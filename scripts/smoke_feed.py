"""Stand-in for vdev when testing the server alone. Not the simulator (that is EMB's).

  history: N days of minute frames (type 2, history bit) for crew 1–6, 2 days for crew 7
  live:    M minutes of second frames for crew 1, optionally with a hypoxia ramp

  python -m scripts.smoke_feed --url ws://localhost:8000/ingest --days 14 --live-min 20 --hypoxia
"""

import argparse
import asyncio
import math
import random
import time

import websockets

from src.vigil_types.ingest.frame import (
    FLAG_HISTORY,
    FLAG_TRAINING,
    FLAG_WORN,
    TYPE_MINUTE,
    TYPE_SECOND,
    Frame,
    encode,
)

REST_HR = {1: 58, 2: 62, 3: 66, 4: 54, 5: 60, 6: 64, 7: 57}


def body(crew: int, ts: int, rng: random.Random) -> dict:
    h = ts % 86400 / 3600
    hr0 = REST_HR[crew]
    if h >= 22 or h < 6:  # sleep
        hr, act, flags = hr0 - 10 + rng.gauss(0, 1), 3 + rng.random() * 3, FLAG_WORN
    elif 10 <= h < 10.75 or 17 <= h < 17.75:  # scheduled exercise
        hr, act, flags = hr0 + 60 + rng.gauss(0, 5), 200 + rng.random() * 50, FLAG_WORN | FLAG_TRAINING
    else:
        hr, act, flags = hr0 + 3 * math.sin(h) + rng.gauss(0, 1.5), 20 + rng.random() * 10, FLAG_WORN
    return dict(hr=hr, spo2=97.5 + rng.gauss(0, 0.4), rr=14 + rng.gauss(0, 0.6), skin_t=33.5 + rng.gauss(0, 0.1),
                co2_ppm=2400 + rng.gauss(0, 100), press_hpa=1013 + rng.gauss(0, 0.3), act_mg=act,
                sqi=95, flags=flags, batt_pct=90, hrv=45 + rng.gauss(0, 3), amb_t=22.5)


async def history(ws, days: int, end_ts: int) -> int:
    rng = random.Random(1)
    n = 0
    seq = {c: 0 for c in REST_HR}
    for crew in REST_HR:
        d = 2 if crew == 7 else days
        for ts in range(end_ts - d * 86400, end_ts, 60):
            b = body(crew, ts, rng)
            b["flags"] |= FLAG_HISTORY
            seq[crew] = (seq[crew] + 1) % 256
            await ws.send(encode(Frame(type=TYPE_MINUTE, dev_id=crew, ts=ts, seq=seq[crew], **b)))
            n += 1
    return n


async def live(ws, start_ts: int, minutes: int, hypoxia: bool, realtime: bool) -> None:
    rng = random.Random(2)
    for s in range(minutes * 60):
        ts = start_ts + s
        b = body(1, ts, rng)
        b["flags"] &= ~FLAG_TRAINING
        b["act_mg"] = 20
        if hypoxia and s >= 120:  # ramp spo2 down to ~86 over 10 minutes
            drop = min(11.5, (s - 120) / 600 * 11.5)
            b["spo2"] -= drop
            b["hr"] += drop
        await ws.send(encode(Frame(type=TYPE_SECOND, dev_id=1, ts=ts, seq=s % 256, **b)))
        if realtime:
            await asyncio.sleep(1)


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="ws://localhost:8000/ingest")
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--live-min", type=int, default=0)
    p.add_argument("--hypoxia", action="store_true")
    p.add_argument("--realtime", action="store_true")
    p.add_argument("--end-ts", type=int, default=1794614400)  # 2026-11-14 00:00 UTC
    a = p.parse_args()
    async with websockets.connect(a.url, max_size=None) as ws:
        if a.days:
            t = time.perf_counter()
            n = await history(ws, a.days, a.end_ts)
            print(f"history: {n} minute frames in {time.perf_counter() - t:.1f}s")
        if a.live_min:
            await live(ws, a.end_ts + 8 * 3600, a.live_min, a.hypoxia, a.realtime)
            print(f"live: {a.live_min} min of seconds sent")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
