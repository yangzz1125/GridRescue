# Real event replay — event_002

## Case

- OEDI/EAGLE-I event: `California-16`, Sacramento County, California.
- Event type: `Severe Weather`.
- Event window: 2023-01-08 07:00–15:15 UTC, 8.25 h.
- Peak reported customers: 348,829.
- Weather: Open-Meteo historical archive, Sacramento point `(38.58, -121.49)`,
  2023-01-07 through 2023-01-09 UTC, 72 hourly rows.

Files are under `data/events/event_002/`. The case is paired with Texas
`event_001` in `data/events/real_event_comparison.csv`.

## Reproduce

```text
python scripts/real_event_replay.py --event-dir data/events/event_002 --weather-csv data/events/event_002/weather_sacramento_20230107_20230109.csv --event-id California-16 --county Sacramento --year 2023
```

## Interpretation

The 33-node translation uses the same explicit regional proxy as event_001:
`peak_customers / reference_customers` with reference denominator 4,000,000,
then deterministic representative branch selection and 24-hour repair-window
compression. These branches are not claimed to be the actual Sacramento
feeder lines. All outputs remain `E_external_aggregate` and
`regional_statistical_mapping`.

The two-event comparison is a robustness check, not a statistical estimate of
all U.S. outages. It tests whether the strategy ordering and carbon/resilience
trade-off are stable across two independent public event records.
