#!/usr/bin/env python3
"""Back-adjust daily prices for splits, bonuses and cash dividends, and find unadjusted splits.

Part of claude-market-data-skills by Viprasol Tech Private Limited.

Prices CSV: date, open, high, low, close[, volume] (raw, unadjusted, ascending or not).
Actions CSV: ex_date, type, value
  split     value = new shares per old share (2-for-1 split -> 2; 1-for-10 reverse -> 0.1)
  bonus     value = bonus shares per share held (1:1 bonus -> 1, i.e. a 2x split)
  dividend  value = cash per share (same currency as prices)

Method (multiplicative, CRSP/Yahoo style): for each action, every row BEFORE
the ex-date is scaled. Split/bonus: prices / ratio, volume x ratio. Dividend:
prices x (1 - D / close of the last trading day before the ex-date).
Factors compound backwards, so the latest prices are unchanged.

  python adjust_prices.py prices.csv --actions actions.csv --out adjusted.csv
  python adjust_prices.py prices.csv --scan            # look for likely unadjusted splits
  python adjust_prices.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import decimal
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from fractions import Fraction

decimal.getcontext().prec = 60   # many compounded actions need more than the default 28 digits


def _d(text: str, what: str) -> Decimal:
    try:
        v = Decimal(text.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"bad {what}: {text!r}") from None
    if not v.is_finite():
        raise ValueError(f"bad {what}: {text!r}")
    return v


def load_prices(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), start=2):
            try:
                row = {"date": date.fromisoformat(r["date"].strip()[:10])}
                for k in ("open", "high", "low", "close"):
                    row[k] = _d(r[k], k)
                row["volume"] = _d(r["volume"], "volume") if r.get("volume") not in (None, "") else None
            except (KeyError, ValueError) as exc:
                raise ValueError(f"prices line {i}: {exc}") from None
            rows.append(row)
    rows.sort(key=lambda x: x["date"])
    for a, b in zip(rows, rows[1:]):
        if a["date"] == b["date"]:
            raise ValueError(f"duplicate date {a['date']}")
    return rows


def load_actions(path: str) -> list[dict]:
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), start=2):
            try:
                t = r["type"].strip().lower()
                v = _d(r["value"], "value")
                if t not in {"split", "bonus", "dividend"} or v <= 0:
                    raise ValueError("type must be split, bonus or dividend and value > 0")
                out.append({"ex_date": date.fromisoformat(r["ex_date"].strip()[:10]), "type": t, "value": v})
            except (KeyError, ValueError) as exc:
                raise ValueError(f"actions line {i}: {exc}") from None
    return out


def factors(rows: list[dict], actions: list[dict]) -> tuple[list[Decimal], list[Decimal], list[str]]:
    """Per-row price and volume multipliers, plus warnings."""
    n = len(rows)
    pf = [Decimal(1)] * n
    vf = [Decimal(1)] * n
    warnings = []
    seen = set()
    same_day_ratio: dict[date, Decimal] = {}
    # within an ex-date, splits/bonuses first: a same-day dividend is paid per post-split share
    for act in sorted(actions, key=lambda a: (a["ex_date"], a["type"] == "dividend")):
        key = (act["ex_date"], act["type"], act["value"])
        if key in seen:
            warnings.append(f"{act['ex_date']}: duplicate {act['type']} {act['value']} applied twice; check the actions file")
        seen.add(key)
        before = [i for i, r in enumerate(rows) if r["date"] < act["ex_date"]]
        if not before:
            continue
        if act["type"] in {"split", "bonus"}:
            ratio = act["value"] if act["type"] == "split" else 1 + act["value"]
            same_day_ratio[act["ex_date"]] = same_day_ratio.get(act["ex_date"], Decimal(1)) * ratio
            p, v = 1 / ratio, ratio
        else:
            prev_close = rows[before[-1]]["close"] / same_day_ratio.get(act["ex_date"], Decimal(1))
            if act["value"] >= prev_close:
                warnings.append(f"{act['ex_date']}: dividend {act['value']} >= previous close {prev_close}; skipped")
                continue
            p, v = 1 - act["value"] / prev_close, Decimal(1)
        if not any(r["date"] >= act["ex_date"] for r in rows):
            warnings.append(f"{act['ex_date']}: ex-date after the last price row; applied to all rows")
        for i in before:
            pf[i] *= p
            vf[i] *= v
    return pf, vf, warnings


def adjust(rows: list[dict], actions: list[dict]) -> tuple[list[dict], list[str]]:
    pf, vf, warnings = factors(rows, actions)
    out = []
    for r, p, v in zip(rows, pf, vf):
        a = {"date": r["date"], "factor": p}
        for k in ("open", "high", "low", "close"):
            a[k] = r[k] * p
        a["volume"] = r["volume"] * v if r["volume"] is not None else None
        out.append(a)
    return out, warnings


def scan(rows: list[dict], tolerance: float = 0.03, min_gap: float = 0.3) -> list[str]:
    """Overnight gaps (open vs previous close) of 30%+ that sit within 3% of a p-for-q ratio, p, q <= 50."""
    hits = []
    for a, b in zip(rows, rows[1:]):
        if a["close"] <= 0 or b["open"] <= 0:
            continue
        r = float(a["close"] / b["open"])          # > 1: split (more shares), < 1: reverse split
        if abs(r - 1) < min_gap:
            continue
        cands = [(abs(r / (n / q) - 1), q, Fraction(n, q)) for q in range(1, 51) for n in [round(r * q)]
                 if 1 <= n <= 50 and abs(r / (n / q) - 1) <= tolerance]
        if not cands:
            continue
        best = min(c[0] for c in cands)
        f = min((c for c in cands if c[0] <= best + 0.002), key=lambda c: c[1])[2]   # closest, then simplest
        hits.append(f"{b['date']}: previous close {a['close']} -> open {b['open']} "
                    f"(x{1 / r:.4f}), looks like a {f.numerator}-for-{f.denominator} "
                    f"{'split' if r > 1 else 'reverse split'}; check corporate actions")
    return hits


def fmt(d: Decimal) -> str:
    """Plain decimal text without exponent notation or trailing zeros (100, not 1E+2)."""
    t = format(d.normalize(), "f")
    return t


def _self_test() -> None:
    D = Decimal

    def row(d, c, vol="1000"):
        return {"date": date.fromisoformat(d), "open": D(c), "high": D(c), "low": D(c), "close": D(c), "volume": D(vol)}

    rows = [row("2026-01-05", "200"), row("2026-01-06", "202"), row("2026-01-07", "101"), row("2026-01-08", "100")]
    adj, w = adjust(rows, [{"ex_date": date(2026, 1, 7), "type": "split", "value": D(2)}])
    assert [a["close"] for a in adj] == [D(100), D(101), D(101), D(100)] and not w, adj
    assert adj[0]["volume"] == D(2000) and adj[3]["volume"] == D(1000)
    # 1:1 bonus is a 2x split
    adj2, _ = adjust(rows, [{"ex_date": date(2026, 1, 7), "type": "bonus", "value": D(1)}])
    assert [a["close"] for a in adj2] == [a["close"] for a in adj]
    # dividend: factor (1 - D / previous close), applied before the ex-date only
    rows = [row("2026-02-02", "50"), row("2026-02-03", "50"), row("2026-02-04", "49")]
    adj, _ = adjust(rows, [{"ex_date": date(2026, 2, 4), "type": "dividend", "value": D(1)}])
    assert adj[1]["close"] == D(49) and adj[0]["close"] == D(49) and adj[2]["close"] == D(49), adj
    # both, compounding backwards; latest unchanged
    rows = [row("2026-03-02", "100"), row("2026-03-03", "100"), row("2026-03-04", "50"), row("2026-03-05", "50")]
    acts = [{"ex_date": date(2026, 3, 4), "type": "split", "value": D(2)},
            {"ex_date": date(2026, 3, 5), "type": "dividend", "value": D("0.5")}]
    adj, _ = adjust(rows, acts)
    assert adj[3]["close"] == D(50) and adj[2]["close"] == D("49.5") and adj[0]["close"] == D("49.5"), adj
    # scan finds an unadjusted 2:1 split and a 1:10 reverse split, ignores a normal 3% move
    rows = [row("2026-04-01", "300"), row("2026-04-02", "151"), row("2026-04-03", "155"), row("2026-04-06", "1540")]
    hits = scan(rows)
    assert len(hits) == 2 and "2026-04-02" in hits[0] and "2026-04-06" in hits[1], hits
    for prev, nxt, label in (("700", "100", "7-for-1"), ("2000", "100", "20-for-1"), ("10", "30", "1-for-3"),
                             ("2", "100", "1-for-50"), ("150", "100", "3-for-2")):
        h = scan([row("2026-05-01", prev), row("2026-05-04", nxt)])
        assert h and label in h[0], (prev, nxt, h)
    assert not scan([row("2026-05-01", "100"), row("2026-05-04", "80")])          # a 20% drop is not a split
    # split and dividend on the same ex-date: dividend is per post-split share
    rows = [row("2026-03-05", "100"), row("2026-03-06", "49")]
    adj, _ = adjust(rows, [{"ex_date": date(2026, 3, 6), "type": "dividend", "value": D(1)},
                           {"ex_date": date(2026, 3, 6), "type": "split", "value": D(2)}])
    assert adj[0]["factor"] == D("0.49"), adj
    _, w = adjust(rows, [{"ex_date": date(2026, 3, 6), "type": "dividend", "value": D(1)}] * 2)
    assert any("duplicate" in x for x in w), w
    many = [{"ex_date": date(2026, 3, 6), "type": "split", "value": D("0.1")}] * 24
    adj, _ = adjust(rows, many)
    assert fmt(adj[0]["close"].quantize(D("0.000001")))
    _, w = adjust(rows, [{"ex_date": date(2026, 4, 2), "type": "dividend", "value": D(400)}])
    assert w and "skipped" in w[0]
    assert fmt(Decimal("100.000000")) == "100" and fmt(Decimal("2200")) == "2200" and fmt(Decimal("0.50")) == "0.5"
    print("adjust_prices self-test passed")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Back-adjust prices for corporate actions; scan for unadjusted splits")
    ap.add_argument("prices", nargs="?")
    ap.add_argument("--actions", help="Corporate actions CSV (ex_date,type,value)")
    ap.add_argument("--out", help="Write adjusted CSV here (default: stdout)")
    ap.add_argument("--scan", action="store_true", help="Report overnight gaps that look like splits")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        _self_test()
        return 0
    if not a.prices or not (a.actions or a.scan):
        ap.print_help()
        return 2
    try:
        rows = load_prices(a.prices)
        if a.scan:
            hits = scan(rows)
            print("\n".join(hits) if hits else "no split-like gaps found")
            if not a.actions:
                return 1 if hits else 0
        adj, warnings = adjust(rows, load_actions(a.actions))
    except (ValueError, OSError, ArithmeticError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for w in warnings:
        print("warning:", w, file=sys.stderr)
    fh = open(a.out, "w", newline="", encoding="utf-8") if a.out else sys.stdout
    try:
        wr = csv.writer(fh)
        wr.writerow(["date", "open", "high", "low", "close", "volume", "factor"])
        for r in adj:
            q = Decimal("0.000001")
            wr.writerow([r["date"].isoformat()] + [fmt(r[k].quantize(q)) for k in ("open", "high", "low", "close")]
                        + ["" if r["volume"] is None else fmt(r["volume"]), fmt(r["factor"].quantize(Decimal("1e-10")))])
    finally:
        if a.out:
            fh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
