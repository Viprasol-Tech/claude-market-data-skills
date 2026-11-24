#!/usr/bin/env python3
"""Find the data problems that quietly break backtests: a quality report for OHLCV bars.

Part of claude-market-data-skills by Viprasol Tech Private Limited.

Checks: unparseable rows, non-positive prices, OHLC inconsistency (high below
open/close, low above), duplicate and out-of-order timestamps, gaps against an
expected bar interval and session, frozen bars (identical OHLC repeated),
zero-volume runs, and return outliers (robust z-score on log returns).

  python bar_check.py bars.csv --interval 1m --session 09:15-15:30 --tz +05:30
  python bar_check.py daily.csv --interval 1d --holidays nse_holidays.txt
  python bar_check.py --self-test

CSV columns: time (ISO 8601; date only for daily), open, high, low, close[, volume].
Exit code 1 when an error-level problem is found.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
import sys
from datetime import date, datetime, time, timedelta, timezone

MAX_GAP_STEPS = 2_000_000
INTERVALS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "1d": 86400}


def parse_offset(text: str):
    m = re.fullmatch(r"([+-])(\d\d):?(\d\d)", text)
    if not m:
        raise ValueError(f"--tz must be an offset like +05:30, got {text!r}")
    sign = 1 if m.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3))))


def load(path: str, tz=timezone.utc) -> tuple[list[dict], list[str]]:
    """Timestamps without an offset (and plain dates) are read in the exchange zone `tz`."""
    rows, errors = [], []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), start=2):
            try:
                t = r["time"].strip()
                ts = datetime.fromisoformat(t.replace("Z", "+00:00"))
                ts = ts if ts.tzinfo else ts.replace(tzinfo=tz)
                o, h, lo, c = (float(r[k]) for k in ("open", "high", "low", "close"))
                v = float(r["volume"]) if r.get("volume") not in (None, "") else None
                if not all(math.isfinite(x) for x in (o, h, lo, c)) or (v is not None and not math.isfinite(v)):
                    raise ValueError("non-finite number")
            except (KeyError, ValueError) as exc:
                errors.append(f"line {i}: unparseable ({exc})")
                continue
            rows.append({"line": i, "ts": ts, "o": o, "h": h, "l": lo, "c": c, "v": v})
    return rows, errors


def check(rows: list[dict], interval: int, session: tuple[time, time] | None, tz, holidays: set[date],
          z_limit: float = 8.0) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for r in rows:
        if min(r["o"], r["h"], r["l"], r["c"]) <= 0:
            errors.append(f"line {r['line']}: non-positive price")
        if r["h"] < max(r["o"], r["c"]) or r["l"] > min(r["o"], r["c"]) or r["l"] > r["h"]:
            errors.append(f"line {r['line']}: OHLC inconsistent (o={r['o']} h={r['h']} l={r['l']} c={r['c']})")
        if r["v"] is not None and r["v"] < 0:
            errors.append(f"line {r['line']}: negative volume")
    for a, b in zip(rows, rows[1:]):
        if b["ts"] == a["ts"]:
            errors.append(f"line {b['line']}: duplicate timestamp {b['ts'].isoformat()}")
        elif b["ts"] < a["ts"]:
            errors.append(f"line {b['line']}: out of order ({b['ts'].isoformat()} after {a['ts'].isoformat()})")
    srt = sorted({r["ts"]: r for r in rows}.values(), key=lambda r: r["ts"])
    # gaps
    missing = 0
    examples = []
    steps = 0
    capped = False
    for a, b in zip(srt, srt[1:]):
        t = a["ts"] + timedelta(seconds=interval)
        while t < b["ts"] and not capped:
            if expected(t, interval, session, tz, holidays):
                missing += 1
                if len(examples) < 5:
                    examples.append(t.astimezone(tz).isoformat())
            t += timedelta(seconds=interval)
            steps += 1
            capped = steps >= MAX_GAP_STEPS
        if capped:
            break
    if missing:
        warnings.append(f"{'at least ' if capped else ''}{missing} expected bar(s) missing, e.g. {', '.join(examples)} "
                        "(check holidays/session)")
    if capped:
        warnings.append(f"gap scan stopped after {MAX_GAP_STEPS:,} steps: the file spans far more time than its bars "
                        "(a stray old timestamp?)")
    # bars outside the session or on holidays
    outside = [r for r in srt if not expected(r["ts"], interval, session, tz, holidays)]
    if outside:
        warnings.append(f"{len(outside)} bar(s) outside the session or on non-trading days, first {outside[0]['ts'].isoformat()}")
    # frozen bars and zero-volume runs
    run = 1
    for a, b in zip(srt, srt[1:]):
        same = (a["o"], a["h"], a["l"], a["c"]) == (b["o"], b["h"], b["l"], b["c"]) and a["o"] != a["h"]
        run = run + 1 if same else 1
        if run == 3:
            warnings.append(f"identical non-flat bars repeated from {a['ts'].isoformat()}: stale feed or forward-fill")
    zero = [r for r in srt if r["v"] == 0]
    if len(zero) > max(3, len(srt) // 20):
        warnings.append(f"{len(zero)} zero-volume bars ({len(zero) / len(srt):.0%}): forward-filled or illiquid")
    # return outliers, robust z-score (median absolute deviation)
    rets = [(b, math.log(b["c"] / a["c"])) for a, b in zip(srt, srt[1:]) if a["c"] > 0 and b["c"] > 0]
    if len(rets) >= 20:
        vals = [x for _, x in rets]
        med = statistics.median(vals)
        # robust scale: the larger of MAD/0.6745 and IQR/1.349 (both estimate sigma for normal data;
        # IQR stays sensible when returns cluster on a few values), stdev only if both are zero
        q1, _, q3 = statistics.quantiles(vals, n=4)
        scale = max(statistics.median(abs(x - med) for x in vals) / 0.6745, (q3 - q1) / 1.349)
        # scale 0: most bars unchanged (illiquid); any move would look infinite, so skip the test
        for r, x in rets:
            if scale < 1e-12:
                break
            z = (x - med) / scale
            if abs(z) > z_limit:
                warnings.append(f"line {r['line']}: return {math.expm1(x):+.1%} (robust z {z:.0f}): bad tick, "
                                "unadjusted split or real gap? check corporate actions")
    return errors, warnings


def expected(ts: datetime, interval: int, session, tz, holidays: set[date]) -> bool:
    """Is a bar expected at ts? Sessions may cross midnight (start > end): the part after
    `start` belongs to the NEXT day's session (e.g. CME 18:00-17:00, Sunday evening = Monday)."""
    local = ts.astimezone(tz)
    day = local.date()
    if interval < 86400 and session is not None:
        start, end = session
        t = local.time()
        if start <= end:
            if not (start <= t < end):
                return False
        else:
            if t >= start:
                day = day + timedelta(days=1)
            elif not (t < end):
                return False
    return day.weekday() < 5 and day not in holidays


def _self_test() -> None:
    ist = parse_offset("+05:30")
    base = datetime(2026, 11, 23, 9, 15, tzinfo=ist)
    rows = []
    price = 100.0
    for i in range(40):
        price *= 1.001 if i % 2 else 0.9995
        rows.append({"line": i + 2, "ts": base + timedelta(minutes=i), "o": price, "h": price * 1.001,
                     "l": price * 0.999, "c": price, "v": 100.0})
    sess = (time(9, 15), time(15, 30))
    e, w = check(rows, 60, sess, ist, set())
    assert not e and not w, (e, w)
    bad = [dict(r) for r in rows]
    bad[5]["h"] = bad[5]["o"] * 0.9                    # high below open
    bad[10]["ts"] = bad[9]["ts"]                        # duplicate
    del bad[20:23]                                       # 3 missing bars
    bad[30]["c"] = bad[30]["c"] / 2                      # split-like drop
    bad[30]["l"] = bad[30]["c"]
    e, w = check(bad, 60, sess, ist, set())
    assert any("OHLC inconsistent" in x for x in e) and any("duplicate" in x for x in e), e
    assert any("missing" in x for x in w) and any("robust z" in x for x in w), w
    assert sum("robust z" in x for x in w) == 2, w      # the bad bar and the recovery, not the regular moves
    # overnight session (18:00-17:00 ET): Sunday 18:00 belongs to Monday; the 17:00-18:00 break is not a gap
    et = parse_offset("-05:00")
    on = (time(18, 0), time(17, 0))
    assert expected(datetime(2026, 11, 22, 18, 30, tzinfo=et), 60, on, et, set())        # Sunday evening
    assert not expected(datetime(2026, 11, 23, 17, 30, tzinfo=et), 60, on, et, set())    # daily break
    assert not expected(datetime(2026, 11, 20, 18, 30, tzinfo=et), 60, on, et, set())    # Friday evening
    # date-only rows are read in the exchange zone, not UTC
    import os
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8-sig") as fh:
        fh.write("time,open,high,low,close\n" + "".join(f"2026-11-{d},1,1,1,1\n" for d in (16, 17, 18, 19, 20, 23)))
    try:
        loaded, errs = load(fh.name, et)
        assert not errs and not check(loaded, 86400, None, et, set())[1], errs
    finally:
        os.unlink(fh.name)
    # illiquid series (most returns 0): no false outliers
    flat = [{"line": i, "ts": base + timedelta(minutes=i), "o": 10, "h": 10, "l": 10, "c": 10.05 if i == 60 else 10, "v": 1}
            for i in range(120)]
    assert not any("robust z" in x for x in check(flat, 60, None, ist, set())[1])
    # weekend and holiday are not gaps for daily data
    d = [{"line": 2, "ts": datetime(2026, 11, 20, tzinfo=ist), "o": 1, "h": 1, "l": 1, "c": 1, "v": 1},
         {"line": 3, "ts": datetime(2026, 11, 24, tzinfo=ist), "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]
    _, w = check(d, 86400, None, ist, {date(2026, 11, 23)})
    assert not w, w
    _, w = check(d, 86400, None, ist, set())
    assert any("1 expected bar" in x for x in w), w
    print("bar_check self-test passed")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Quality report for OHLCV bars")
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--interval", choices=sorted(INTERVALS), default="1d")
    ap.add_argument("--session", help="HH:MM-HH:MM in --tz (intraday only), e.g. 09:15-15:30; may cross midnight (18:00-17:00)")
    ap.add_argument("--tz", default="+00:00", help="Exchange UTC offset, e.g. +05:30 (no DST handling); also used for timestamps without an offset")
    ap.add_argument("--holidays", help="File with one YYYY-MM-DD per line")
    ap.add_argument("--z", type=float, default=8.0, help="Robust z-score limit for return outliers")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        _self_test()
        return 0
    if not a.csv:
        ap.print_help()
        return 2
    try:
        tz = parse_offset(a.tz)
        session = None
        if a.session:
            s, e = a.session.split("-")
            session = (time.fromisoformat(s), time.fromisoformat(e))
        hol = set()
        if a.holidays:
            with open(a.holidays, encoding="utf-8") as fh:
                hol = {date.fromisoformat(x.split("#")[0].strip()) for x in fh if x.split("#")[0].strip()}
        rows, load_errors = load(a.csv, tz)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors, warnings = check(rows, INTERVALS[a.interval], session, tz, hol, a.z)
    errors = load_errors + errors
    for x in errors:
        print("ERROR  ", x)
    for x in warnings:
        print("WARNING", x)
    print(f"{len(rows)} bars, {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
