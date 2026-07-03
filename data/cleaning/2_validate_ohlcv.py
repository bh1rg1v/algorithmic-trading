"""
2_validate_ohlcv.py
====================
Validates OHLC integrity for every CSV file found under data/storage/.

Checks performed per file:
  1. Schema          – Open, High, Low, Close columns are present
  2. Low <= High     – no candle where Low is greater than High
  3. OHLC integrity  – High >= max(Open, Close)  and  Low <= min(Open, Close)

Optimisations:
  - os.stat()       – zero-I/O empty-file guard (single syscall)
  - Explicit read   – whole file into bytes once; pd.read_csv uses io.BytesIO
  - usecols         – C engine discards non-OHLC columns before Python sees them
  - dtype=float32   – halves RAM; skips post-hoc coerce loop
  - .values         – zero-copy numpy view (no extra allocation)
  - np.maximum/min  – SIMD-vectorised element-wise ops on float32 arrays
  - Single-pass     – build_summary iterates results exactly once
  - Chunk size 2000 – limits Future objects while maximising throughput

Progress:
  Daemon thread refreshes the bar every 50 ms via thread-safe counters,
  so the display updates the moment each file starts processing.

Concurrency:
  ThreadPoolExecutor — I/O + pandas C engine + numpy all release the GIL.
  Worker count: min(64, cpu_count × 4).
"""

import io
import os
import sys
import csv
import time
import threading
import concurrent.futures
from collections import defaultdict
from dataclasses import dataclass, asdict, fields
from datetime import datetime
from typing import List

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE       = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.abspath(os.path.join(_HERE, "..", "storage"))
REPORT_CSV       = os.path.join(_HERE, "ohlcv_validation_report.csv")
SUMMARY_TXT      = os.path.join(_HERE, "ohlcv_validation_summary.txt")
INVALID_ROWS_TXT = os.path.join(_HERE, "ohlcv_invalid_rows.txt")

# ---------------------------------------------------------------------------
# Column aliases  (all lower-cased)
# ---------------------------------------------------------------------------
_OHLC_ALIASES: dict[str, list[str]] = {
    "open":  ["open",  "o"],
    "high":  ["high",  "h"],
    "low":   ["low",   "l"],
    "close": ["close", "cl", "c"],
}

REQUIRED_COLS = list(_OHLC_ALIASES.keys())   # ['open','high','low','close']

# Flat frozenset — O(1) membership test in the usecols callable (built once)
_ALL_ALIASES: frozenset[str] = frozenset(
    alias for aliases in _OHLC_ALIASES.values() for alias in aliases
)


def _is_ohlc_col(col_name: str) -> bool:
    """usecols callable: keep a column only if its name matches an OHLC alias."""
    return col_name.lower() in _ALL_ALIASES


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    file_path:                 str  = ""
    rel_path:                  str  = ""
    source_type:               str  = ""
    total_rows:                int  = 0
    is_empty:                  bool = False
    is_header_only:            bool = False
    missing_cols:              str  = ""    # comma-sep list
    schema_ok:                 bool = True
    low_gt_high_rows:          int  = 0
    ohlc_integrity_violations: int  = 0
    passed:                    bool = True
    failure_reasons:           str  = ""   # pipe-sep list
    # Detail of invalid rows — excluded from CSV report, written to separate txt
    invalid_rows_detail:       str  = ""

    def mark_fail(self, reason: str) -> None:
        self.passed = False
        if self.failure_reasons:
            if reason not in self.failure_reasons:
                self.failure_reasons += "|" + reason
        else:
            self.failure_reasons = reason


# ---------------------------------------------------------------------------
# Thread-safe progress counters
# Three plain ints guarded by one lock — faster than dict key lookups.
# ---------------------------------------------------------------------------
_prog_lock    = threading.Lock()
_prog_started = 0
_prog_passed  = 0
_prog_failed  = 0


def _tick_started() -> None:
    global _prog_started
    with _prog_lock:
        _prog_started += 1


def _tick_done(passed: bool) -> None:
    global _prog_passed, _prog_failed
    with _prog_lock:
        if passed:
            _prog_passed += 1
        else:
            _prog_failed += 1


# ---------------------------------------------------------------------------
# Core validation  (runs inside a worker thread)
# ---------------------------------------------------------------------------
def validate_file(file_path: str, rel_path: str, source_type: str) -> ValidationResult:
    # ← fires immediately when the file starts being processed
    _tick_started()

    result = ValidationResult(file_path=file_path, rel_path=rel_path, source_type=source_type)

    # ------------------------------------------------------------------
    # 0. Empty-file guard — os.stat is a single syscall, no file open
    # ------------------------------------------------------------------
    try:
        size = os.stat(file_path).st_size
    except OSError as exc:
        result.mark_fail(f"stat_error:{exc}")
        _tick_done(result.passed)
        return result

    if size == 0:
        result.is_empty = True
        result.mark_fail("empty_file")
        _tick_done(result.passed)
        return result

    # ------------------------------------------------------------------
    # 1. Read entire file into RAM once
    #    All subsequent work (pandas, numpy) operates on this buffer —
    #    no further disk I/O, keeps bytes pinned in RAM during processing.
    # ------------------------------------------------------------------
    try:
        with open(file_path, "rb") as fh:
            raw = fh.read()
    except Exception as exc:
        result.mark_fail(f"read_error:{exc}")
        _tick_done(result.passed)
        return result

    # ------------------------------------------------------------------
    # 2. Single-pass CSV parse from in-memory BytesIO
    #    usecols callable → C engine drops non-OHLC cols before Python sees them
    #    dtype=float32    → no post-hoc coerce; halves array memory footprint
    # ------------------------------------------------------------------
    try:
        df = pd.read_csv(
            io.BytesIO(raw),
            usecols=_is_ohlc_col,
            dtype=np.float32,
            on_bad_lines="skip",
            engine="c",
        )
    except Exception as exc:
        result.mark_fail(f"parse_error:{exc}")
        _tick_done(result.passed)
        return result

    # Release the raw bytes immediately — DataFrame has its own copy
    del raw

    # ------------------------------------------------------------------
    # 3. Schema: confirm all four OHLC columns were found
    # ------------------------------------------------------------------
    col_lower = {c.lower(): c for c in df.columns}
    col_map: dict[str, str] = {}
    for canonical, aliases in _OHLC_ALIASES.items():
        for alias in aliases:
            if alias in col_lower:
                col_map[canonical] = col_lower[alias]
                break

    missing = [c for c in REQUIRED_COLS if c not in col_map]
    if missing:
        result.schema_ok = False
        result.missing_cols = ",".join(missing)
        result.mark_fail("missing_columns")
        _tick_done(result.passed)
        return result

    # ------------------------------------------------------------------
    # 4. Zero-copy numpy views — float32 arrays already owned by DataFrame
    # ------------------------------------------------------------------
    o: np.ndarray = df[col_map["open"]].values
    h: np.ndarray = df[col_map["high"]].values
    l: np.ndarray = df[col_map["low"]].values
    c: np.ndarray = df[col_map["close"]].values

    # Free the DataFrame — numpy arrays hold their own memory
    del df

    # Drop NaN rows and remember their original 0-based positions so we can
    # report accurate CSV line numbers (line = index + 2: +1 header, +1 for 1-based)
    nan_mask    = np.isnan(o) | np.isnan(h) | np.isnan(l) | np.isnan(c)
    valid_idx   = np.where(~nan_mask)[0]   # original positions in the data array
    o, h, l, c = o[valid_idx], h[valid_idx], l[valid_idx], c[valid_idx]

    result.total_rows = len(valid_idx)

    if result.total_rows == 0:
        result.is_header_only = True   # flagged for reporting, not a failure
        _tick_done(result.passed)
        return result

    # ------------------------------------------------------------------
    # 5. Low <= High
    # ------------------------------------------------------------------
    low_gt_high = l > h
    result.low_gt_high_rows = int(low_gt_high.sum())
    if result.low_gt_high_rows:
        result.mark_fail("low_gt_high")

    # ------------------------------------------------------------------
    # 6. OHLC integrity:  H >= max(O,C)  and  L <= min(O,C)
    #    np.maximum / np.minimum: element-wise SIMD ops on float32
    # ------------------------------------------------------------------
    ohlc_viol = (h < np.maximum(o, c)) | (l > np.minimum(o, c))
    result.ohlc_integrity_violations = int(ohlc_viol.sum())
    if result.ohlc_integrity_violations:
        result.mark_fail("ohlc_integrity")

    # ------------------------------------------------------------------
    # 7. Build per-row detail for any invalid rows (capped at 500)
    # ------------------------------------------------------------------
    _MAX_DETAIL_ROWS = 500
    invalid_mask = low_gt_high | ohlc_viol
    if invalid_mask.any():
        inv_idx  = valid_idx[invalid_mask]   # original 0-based positions
        inv_o    = o[invalid_mask]
        inv_h    = h[invalid_mask]
        inv_l    = l[invalid_mask]
        inv_c    = c[invalid_mask]
        inv_lgh  = low_gt_high[invalid_mask]
        inv_ohlc = ohlc_viol[invalid_mask]

        total_inv = len(inv_idx)
        cap       = min(total_inv, _MAX_DETAIL_ROWS)
        detail_lines: list[str] = []
        for i in range(cap):
            csv_line = int(inv_idx[i]) + 2   # +1 header row, +1 for 1-based
            tags: list[str] = []
            if inv_lgh[i]:
                tags.append("low_gt_high")
            if inv_ohlc[i]:
                tags.append("ohlc_integrity")
            detail_lines.append(
                f"  Line {csv_line:>7,}: "
                f"O={inv_o[i]:>10.4f}  H={inv_h[i]:>10.4f}  "
                f"L={inv_l[i]:>10.4f}  C={inv_c[i]:>10.4f}  "
                f"[{', '.join(tags)}]"
            )
        if total_inv > _MAX_DETAIL_ROWS:
            detail_lines.append(
                f"  ... and {total_inv - _MAX_DETAIL_ROWS:,} more invalid rows (showing first {_MAX_DETAIL_ROWS})"
            )
        result.invalid_rows_detail = "\n".join(detail_lines)

    _tick_done(result.passed)
    return result


# ---------------------------------------------------------------------------
# File collector
# ---------------------------------------------------------------------------
_SKIP_DIRS: frozenset[str] = frozenset(["fundamentals", "raw", "2014-2024"])


def collect_all_files(storage_dir: str) -> list:
    """Iterative scandir walk; tags each CSV with a source_type string."""
    all_files: list = []
    base_len = len(storage_dir) + 1
    try:
        for entry in os.scandir(storage_dir):
            if not entry.is_dir(follow_symlinks=False):
                continue
            if entry.name.lower() in _SKIP_DIRS:
                continue
            top_name = entry.name.lower()
            stack = [(entry.path, top_name)]
            while stack:
                curr_path, curr_type = stack.pop()
                try:
                    for sub in os.scandir(curr_path):
                        if sub.is_dir(follow_symlinks=False):
                            stack.append((sub.path, f"{curr_type}/{sub.name.lower()}"))
                        elif sub.is_file(follow_symlinks=False) and sub.name.lower().endswith(".csv"):
                            all_files.append((sub.path, sub.path[base_len:], curr_type))
                except PermissionError:
                    pass
    except Exception as exc:
        print(f"[ERROR] Cannot scan storage directory: {exc}")
    return all_files


# ---------------------------------------------------------------------------
# Progress bar  (called from daemon thread only)
# ---------------------------------------------------------------------------
def _progress(current: int, total: int, passed: int, failed: int, width: int = 45) -> None:
    pct    = 100.0 * current / total if total > 0 else 100.0
    filled = int(width * current // max(total, 1))
    bar    = "█" * filled + "─" * (width - filled)
    sys.stdout.write(
        f"\rProgress |{bar}| {pct:5.1f}%  {current:,}/{total:,}  "
        f"✔ {passed:,}  ✘ {failed:,}"
    )
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Progress daemon  — background thread, polls counters every 50 ms
# ---------------------------------------------------------------------------
def _progress_daemon(total: int, stop_evt: threading.Event) -> None:
    """Refresh the progress bar independently of chunk boundaries."""
    while not stop_evt.wait(timeout=0.05):   # wake every 50 ms or on stop
        with _prog_lock:
            s, p, f = _prog_started, _prog_passed, _prog_failed
        _progress(s, total, p, f)
    # Final flush to 100 %
    with _prog_lock:
        p, f = _prog_passed, _prog_failed
    _progress(total, total, p, f)
    sys.stdout.write("\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------
# _REPORT_FIELDS excludes invalid_rows_detail — that goes to the txt report only
_REPORT_FIELDS = [
    fld.name for fld in fields(ValidationResult)
    if fld.name != "invalid_rows_detail"
]


def write_csv_report(results: List[ValidationResult], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(
            {k: v for k, v in asdict(r).items() if k != "invalid_rows_detail"}
            for r in results
        )


def write_invalid_rows_report(results: List[ValidationResult], path: str) -> None:
    """Write filenames + per-row violation detail for every failed file."""
    sep = "=" * 80
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("OHLC INVALID ROWS REPORT\n")
        fh.write(f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        fh.write(sep + "\n")
        invalid = [r for r in results if r.invalid_rows_detail]
        fh.write(f"Files with violations: {len(invalid):,}\n\n")
        for r in invalid:
            fh.write(f"{sep}\n")
            fh.write(f"FILE: {r.rel_path}\n")
            fh.write(f"{sep}\n")
            fh.write(r.invalid_rows_detail)
            fh.write("\n\n")


# ---------------------------------------------------------------------------
# Summary  — single pass over results
# ---------------------------------------------------------------------------
def build_summary(results: List[ValidationResult], elapsed: float) -> str:
    total = len(results)
    if total == 0:
        return "No files were processed."

    # ── Single pass: compute all aggregate values at once ──────────────────
    passed = failed = empty = honly = rows = 0
    low_gt_high_total = ohlc_viol_total = 0

    by_source: dict = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0, "honly": 0})
    reason_counts: dict = defaultdict(int)

    for r in results:
        src = by_source[r.source_type]
        src["total"] += 1

        if r.passed:
            passed += 1
            src["passed"] += 1
        else:
            failed += 1
            src["failed"] += 1
            if r.failure_reasons:
                for reason in r.failure_reasons.split("|"):
                    if reason:
                        reason_counts[reason] += 1

        if r.is_empty:
            empty += 1
        if r.is_header_only:
            honly += 1
            src["honly"] += 1

        rows              += r.total_rows
        low_gt_high_total += r.low_gt_high_rows
        ohlc_viol_total   += r.ohlc_integrity_violations

    # ── Format output ───────────────────────────────────────────────────────
    sep   = "=" * 80
    lines = [
        sep, "OHLC VALIDATION SUMMARY", sep,
        f"  Run completed at  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Elapsed time      : {elapsed:.1f}s",
        f"  Storage directory : {STORAGE_DIR}",
        "",
        "Overall Results:",
        f"  Total files       : {total:,}",
        f"  Total rows        : {rows:,}",
        f"  Passed            : {passed:,}  ({100*passed/total:.1f}%)",
        f"  Failed            : {failed:,}  ({100*failed/total:.1f}%)",
        f"  Empty files       : {empty:,}",
        f"  Header-only files : {honly:,}",
        "",
        "Results by Source Type:",
    ]
    for src in sorted(by_source):
        d   = by_source[src]
        pct = 100 * d["passed"] / d["total"] if d["total"] > 0 else 0
        lines.append(
            f"  {src:<35} total={d['total']:>6,}  "
            f"passed={d['passed']:>6,}  failed={d['failed']:>6,}  "
            f"honly={d['honly']:>6,}  ({pct:.1f}% pass)"
        )

    lines += ["", "Failure Reason Breakdown:"]
    if reason_counts:
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {reason:<35} : {count:,} files")
    else:
        lines.append("  (none — all files passed!)")

    lines += [
        "",
        "OHLC Check Totals:",
        f"  {'Low > High rows':<35} : {low_gt_high_total:,}",
        f"  {'OHLC integrity violations':<35} : {ohlc_viol_total:,}",
        f"  {'Header-only files (skipped)':<35} : {honly:,}",
        sep,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not os.path.exists(STORAGE_DIR):
        print(f"[ERROR] Storage directory not found: {STORAGE_DIR}")
        sys.exit(1)

    print(f"Scanning storage directory: {STORAGE_DIR}")
    t0 = time.perf_counter()

    all_files   = collect_all_files(STORAGE_DIR)
    total_files = len(all_files)

    if total_files == 0:
        print("No CSV files found. Exiting.")
        sys.exit(0)

    print(f"Found {total_files:,} CSV files. Starting OHLC validation...\n")

    # I/O-bound — pandas C engine + numpy release the GIL
    num_workers = min(64, (os.cpu_count() or 4) * 4)
    CHUNK_SIZE  = 2000   # ~275 futures for 549k files — low scheduling overhead

    def _chunk_validate(chunk: list) -> list:
        return [validate_file(*args) for args in chunk]

    # Store only chunk length in future_map — don't hold the chunk list twice
    chunks = [all_files[i:i + CHUNK_SIZE] for i in range(0, total_files, CHUNK_SIZE)]

    # Start the progress daemon before the executor so the bar appears immediately
    stop_evt    = threading.Event()
    prog_thread = threading.Thread(
        target=_progress_daemon, args=(total_files, stop_evt), daemon=True, name="progress"
    )
    prog_thread.start()

    all_results: List[ValidationResult] = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Map future → chunk_size (int only — no reference to chunk data)
            future_map = {
                executor.submit(_chunk_validate, chunk): len(chunk)
                for chunk in chunks
            }
            for future in concurrent.futures.as_completed(future_map):
                all_results.extend(future.result())
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted. Writing partial results...")
    finally:
        stop_evt.set()
        prog_thread.join(timeout=1.0)

    elapsed = time.perf_counter() - t0

    print(f"\nWriting CSV report → {REPORT_CSV}")
    try:
        write_csv_report(all_results, REPORT_CSV)
    except Exception as exc:
        print(f"[WARNING] Could not write CSV report: {exc}")

    print(f"Writing invalid rows report → {INVALID_ROWS_TXT}")
    try:
        write_invalid_rows_report(all_results, INVALID_ROWS_TXT)
    except Exception as exc:
        print(f"[WARNING] Could not write invalid rows report: {exc}")

    summary = build_summary(all_results, elapsed)
    print(f"\n{summary}")

    try:
        with open(SUMMARY_TXT, "w", encoding="utf-8") as fh:
            fh.write(summary)
        print(f"Summary saved → {SUMMARY_TXT}")
    except Exception as exc:
        print(f"[WARNING] Could not write summary file: {exc}")

    total_failed = sum(1 for r in all_results if not r.passed)
    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()
