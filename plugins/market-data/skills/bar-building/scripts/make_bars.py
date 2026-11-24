#!/usr/bin/env python3
"""Build time, volume or dollar bars from trades, with explicit labelling rules.

Part of claude-market-data-skills by Viprasol Tech Private Limited.

Trades CSV: time (ISO 8601 with offset, or epoch ms), price, size. Output CSV:
start, end, open, high, low, close, volume, notional, trades.

Rules (state them in your own code too):
  * time bars cover [start, start + interval): a trade exactly on the boundary
    opens the NEXT bar; bars are labelled by their start time, in UTC;
  * intervals are aligned to UTC midnight; use --offset-min to align them to a
    session open instead (hourly bars from NSE's 09:15 IST open = 03:45 UTC:
    --offset-min 45);
  * a period without trades produces NO bar unless --fill, which writes a flat
    bar at the previous close with zero volume (trades = 0); gaps longer than
    --max-fill bars (nights, weekends, halts) are never filled;
  * `end` = start + interval even for the session's last bar: filter trades to
    the session before building bars (NSE hourly bars: the 15:15 bar must not
    absorb trades after 15:30);
  * volume/dollar bars close when the running total reaches the threshold; the
    trade that crosses it belongs to the closing bar (no trade splitting).

  python make_bars.py trades.csv --time 60
  python make_bars.py trades.csv --volume 10000
  python make_bars.py trades.csv --dollar 5000000
  python make_bars.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


MIN_MS, MAX_MS = 0, 4102444800000       # 1970-01-01 .. 2100-01-01


def parse_ts(text: str) -> int:
    """Return epoch milliseconds. Integers: unit guessed from magnitude (s, ms, us, ns)."""
    t = text.strip()
    if t.isdigit():
        v = int(t)
        if v >= 10 ** 17:
            ms = v // 1_000_000          # nanoseconds
        elif v >= 10 ** 14:
            ms = v // 1000               # microseconds
        elif v >= 10 ** 11:
            ms = v                       # milliseconds
        else:
            ms = v * 1000                # seconds
    else:
        d = datetime.fromisoformat(t.replace("Z", "+00:00"))
        if d.tzinfo is None:
            raise ValueError(f"timestamp without a UTC offset: {t!r}")
        ms = int(d.timestamp() * 1000)
    if not MIN_MS <= ms < MAX_MS:
        raise ValueError(f"timestamp out of range 1970-2100: {t!r}")
    return ms


def load(path: str) -> list[tuple[int, Decimal, Decimal]]:
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), start=2):
            try:
                p, q = Decimal(r["price"]), Decimal(r["size"])
                if not (p.is_finite() and q.is_finite()) or p <= 0 or q <= 0:
                    raise ValueError("price and size must be positive")
                out.append((parse_ts(r["time"]), p, q))
            except (KeyError, ValueError, InvalidOperation) as exc:
                raise ValueError(f"line {i}: {exc}") from None
    out.sort(key=lambda x: x[0])   # stable: same-millisecond trades keep file order
    return out


def _new(start, p, q, end=None):
    return {"start": start, "end": end, "open": p, "high": p, "low": p, "close": p,
            "volume": q, "notional": p * q, "trades": 1}


def _add(b, p, q):
    b["high"] = max(b["high"], p)
    b["low"] = min(b["low"], p)
    b["close"] = p
    b["volume"] += q
    b["notional"] += p * q
    b["trades"] += 1


def time_bars(trades, seconds: int, offset_min: int = 0, fill: bool = False, max_fill: int = 60) -> list[dict]:
    step, off = seconds * 1000, offset_min * 60000
    bars: list[dict] = []
    for ts, p, q in trades:
        start = (ts - off) // step * step + off
        if bars and bars[-1]["start"] == start:
            _add(bars[-1], p, q)
            continue
        if fill and bars and (start - bars[-1]["start"]) // step - 1 <= max_fill:   # never fill across a close
            t = bars[-1]["start"] + step
            while t < start:
                c = bars[-1]["close"]
                bars.append({"start": t, "end": t + step, "open": c, "high": c, "low": c, "close": c,
                             "volume": Decimal(0), "notional": Decimal(0), "trades": 0})
                t += step
        bars.append(_new(start, p, q, start + step))
    return bars


def threshold_bars(trades, threshold: Decimal, dollar: bool) -> list[dict]:
    bars: list[dict] = []
    cur = None
    for ts, p, q in trades:
        if cur is None:
            cur = _new(ts, p, q)
        else:
            _add(cur, p, q)
        if (cur["notional"] if dollar else cur["volume"]) >= threshold:
            cur["end"] = ts
            bars.append(cur)
            cur = None
    if cur is not None:
        cur["end"] = None   # incomplete last bar: label it so nobody trades on it
        bars.append(cur)
    return bars


def _self_test() -> None:
    D = Decimal
    t0 = parse_ts("2026-11-24T03:45:00Z")
    trades = [(t0 + 0, D(100), D(5)), (t0 + 30000, D(101), D(5)), (t0 + 59999, D(99), D(5)),
              (t0 + 60000, D(102), D(5)),                          # boundary trade opens the next bar
              (t0 + 180000, D(103), D(5))]                         # minute 2 has no trades
    bars = time_bars(trades, 60)
    assert [b["start"] - t0 for b in bars] == [0, 60000, 180000], bars
    assert (bars[0]["open"], bars[0]["high"], bars[0]["low"], bars[0]["close"], bars[0]["volume"]) == (D(100), D(101), D(99), D(99), D(15))
    filled = time_bars(trades, 60, fill=True)
    assert len(filled) == 4 and filled[2]["trades"] == 0 and filled[2]["close"] == D(102)
    weekend = [(t0, D(1), D(1)), (t0 + 3 * 86400000, D(1), D(1))]
    assert len(time_bars(weekend, 60, fill=True)) == 2          # gap longer than --max-fill: not filled
    for bad in ("2026-11-24T09:15:00", "99999999999999999999", "5000000000000"):
        try:
            parse_ts(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    assert parse_ts("1795511700000000") == parse_ts("1795511700000000000") == 1795511700000      # us, ns
    # hourly bars aligned to the 09:15 IST open (03:45 UTC) vs UTC-aligned (03:00 UTC)
    assert time_bars([(t0 + 60000, D(1), D(1))], 3600, offset_min=45)[0]["start"] == t0
    assert time_bars([(t0 + 60000, D(1), D(1))], 3600)[0]["start"] == t0 - 45 * 60000
    vb = threshold_bars(trades, D(10), dollar=False)
    assert [b["volume"] for b in vb] == [D(10), D(10), D(5)] and vb[-1]["end"] is None, vb
    db = threshold_bars(trades, D(1000), dollar=True)
    assert db[0]["notional"] == D(100 * 5 + 101 * 5) and db[0]["trades"] == 2, db
    assert parse_ts("1795511700") == parse_ts("1795511700000") == parse_ts("2026-11-24T14:45:00+05:30")
    print("make_bars self-test passed")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build time, volume or dollar bars from trades")
    ap.add_argument("csv", nargs="?")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--time", type=int, metavar="SECONDS")
    g.add_argument("--volume", type=Decimal)
    g.add_argument("--dollar", type=Decimal)
    ap.add_argument("--offset-min", type=int, default=0, help="Align time bars to UTC midnight + N minutes")
    ap.add_argument("--fill", action="store_true", help="Emit flat zero-volume bars for empty periods (not across sessions)")
    ap.add_argument("--max-fill", type=int, default=60, help="Only fill gaps of at most this many bars (default 60)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        _self_test()
        return 0
    if not a.csv or (a.time is None and a.volume is None and a.dollar is None):
        ap.print_help()
        return 2
    try:
        trades = load(a.csv)
        if a.time is not None:
            if a.time <= 0:
                raise ValueError("--time must be positive")
            bars = time_bars(trades, a.time, a.offset_min, a.fill, a.max_fill)
        else:
            th = a.volume if a.volume is not None else a.dollar
            if not th.is_finite() or th <= 0:
                raise ValueError("threshold must be positive")
            bars = threshold_bars(trades, th, a.dollar is not None)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    def iso(ms):
        return "" if ms is None else datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="milliseconds")

    w = csv.writer(sys.stdout)
    w.writerow(["start", "end", "open", "high", "low", "close", "volume", "notional", "trades"])
    for b in bars:
        w.writerow([iso(b["start"]), iso(b["end"]), b["open"], b["high"], b["low"], b["close"],
                    b["volume"], b["notional"], b["trades"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
