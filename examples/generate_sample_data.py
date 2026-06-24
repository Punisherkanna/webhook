"""Generate a synthetic EURUSD M15 OHLCV CSV for demos and tests.

Deterministic (seeded) so the backtest output is reproducible. Produces a
trending-with-noise random walk — enough structure for the MA-crossover and RSI
strategies to actually trade.
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta, timezone


def generate(rows: int = 2000, seed: int = 42, start_price: float = 1.1000):
    rng = random.Random(seed)
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    price = start_price
    out = ["timestamp,open,high,low,close,volume"]
    for i in range(rows):
        # Slow sine drift + gaussian noise => trends the strategies can catch.
        drift = math.sin(i / 120.0) * 0.0004
        step = rng.gauss(0, 0.0006) + drift
        o = price
        c = max(0.5, o + step)
        hi = max(o, c) + abs(rng.gauss(0, 0.0003))
        lo = min(o, c) - abs(rng.gauss(0, 0.0003))
        vol = rng.randint(80, 400)
        out.append(f"{t.isoformat()},{o:.5f},{hi:.5f},{lo:.5f},{c:.5f},{vol}")
        price = c
        t += timedelta(minutes=15)
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/EURUSD_M15.csv")
    args = ap.parse_args()
    with open(args.out, "w") as fh:
        fh.write(generate(args.rows, args.seed))
    print(f"wrote {args.rows} bars to {args.out}")


if __name__ == "__main__":
    main()
