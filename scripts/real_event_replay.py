"""CLI wrapper for the checked-in public event replay case."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridrescue.real_event_replay import run_event_replay  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay one OEDI event through GridRescue")
    parser.add_argument("--event-dir", default=str(ROOT / "data/events/event_001"))
    parser.add_argument("--oedi-zip", default=str(ROOT / "data/outage/raw/OEDI_Outage_Dataset_R1.zip"))
    parser.add_argument("--weather-csv", help="weather CSV; defaults to the event directory's first weather_*.csv")
    parser.add_argument("--year", type=int, default=2021)
    parser.add_argument("--event-id", default="Texas-1")
    parser.add_argument("--county", default="Harris")
    parser.add_argument("--reference-customers", type=float, default=4_000_000)
    args = parser.parse_args()
    event_dir = Path(args.event_dir)
    weather_csv = Path(args.weather_csv) if args.weather_csv else next(event_dir.glob("weather_*.csv"))
    replay, mapped, result = run_event_replay(
        oedi_zip=args.oedi_zip,
        weather_csv=weather_csv,
        year=args.year,
        event_id=args.event_id,
        county=args.county,
        reference_customers=args.reference_customers,
        output_dir=event_dir,
    )
    print({
        "event_id": replay.event_id,
        "outage_fraction": replay.outage_fraction,
        "failed_branch_ids_proxy": replay.scenario.failed_branch_ids,
        "mapped_nodes": len(mapped),
        "strategies": list(result.strategies),
        "output_dir": str(event_dir),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
