# Real event replay — event_001

## 1. Case identity

This case joins two public data products by an explicit time/location key:

- **Outage evidence:** OEDI/EAGLE-I Event-correlated Outage Dataset R1,
  archive member `Outage_Dataset/eaglei_outages_with_events_2021.csv`.
- **Weather evidence:** Open-Meteo historical archive, Houston point
  `(29.76, -95.37)`, UTC, 2021-02-15 through 2021-02-17.
- **Selected event:** `Texas-1`, Harris County, event type `Severe Weather`.
- **Selected outage interval:** 2021-02-16 06:15 through 2021-02-17 21:30,
  observed duration 39.25 h, peak 455,986 customers.

Source records:

- OEDI submission 6458: <https://data.openei.org/submissions/6458> (CC BY 4.0).
- Open-Meteo archive endpoint is recorded verbatim in
  `data/events/event_001/weather_metadata.json`; retrieval date is
  2026-08-27 UTC.

Raw and derived files are under:

```text
data/events/event_001/
├─ event_metadata.json
├─ oedi_event_row.csv
├─ weather_houston_20210215_20210217.csv
├─ weather_metadata.json
├─ replay_manifest.json
├─ node_mapping.csv
├─ strategy_comparison.csv
└─ strategy_metrics.csv
```

## 2. Evidence-to-model translation

The U.S. event is **not** a Wuhan feeder incident.  The model translation is
therefore labelled `E_external_aggregate` and
`regional_statistical_mapping` throughout.

1. `peak_customers / reference_customers` produces the explicit regional
   outage fraction.  This case uses `455986 / 4000000 = 0.1139965`.
2. The fraction selects two non-root-side representative branches in the
   IEEE-33 topology (`L4`, `L5`).  This is a severity proxy, not a claim that
   those physical lines failed in Harris County.
3. The 39.25 h observed interval is compressed into the 24 h study horizon as
   two 12 h repair durations.
4. Weather statistics parameterize PV derating, ambient temperature and the
   grid-carbon multiplier.  The hourly weather table itself is retained for
   audit; the feeder has no SCADA/weather station binding.

## 3. Replay outputs

`strategy_comparison.csv` contains the three existing strategies:

- traditional sequential restoration;
- minimum-EENS restoration;
- carbon-resilient coordinated restoration.

The replay executes `run_scenario()` unchanged, so every candidate passes the
same dispatch, island, P/Q, voltage and branch-loading checks as the synthetic
scenarios.  The output is a controlled comparison, not a measured avoided-
emissions claim.

## 4. Reproduce

From the repository root:

```text
python scripts/real_event_replay.py --event-id Texas-1 --county Harris --year 2021
```

The ZIP reader accepts the original archive directly, so no untracked 12 MB
merged CSV extraction is required.

## 5. Claim boundary

This case supports: **public weather + public regional outage statistics +
transparent mapping into the existing 33-node research model**.

It does not support: Wuhan-specific feeder telemetry, hospital measured load,
field crew logs, SCADA control, or third-party verified carbon reduction.
