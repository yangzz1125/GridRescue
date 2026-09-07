"""Map public regional outage observations to the IEEE-33 study model."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from .network import GridModel


OEDI_MERGED_COLUMNS = {
    "fips", "state", "county", "start_time", "duration",
    "min_customers", "max_customers", "mean_customers",
}


def load_oedi_merged(path: str | Path) -> pd.DataFrame:
    """Load an OEDI/EAGLE-I merged event CSV with validated dtypes."""
    frame = pd.read_csv(path)
    missing = sorted(OEDI_MERGED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"OEDI merged file missing columns: {missing}")
    out = frame.copy()
    out["start_time"] = pd.to_datetime(out["start_time"], errors="coerce")
    if out["start_time"].isna().any():
        raise ValueError("OEDI start_time contains invalid timestamps")
    for column in ("duration", "min_customers", "max_customers", "mean_customers"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
        if out[column].isna().any() or (out[column] < 0).any():
            raise ValueError(f"OEDI column {column!r} contains invalid values")
    out["fips"] = out["fips"].astype(str).str.zfill(5)
    return out


def load_oedi_csv_from_zip(
    zip_path: str | Path,
    *,
    internal_path: str = "Outage_Dataset/eaglei_outages_2023_merged.csv",
) -> pd.DataFrame:
    """Load one OEDI CSV directly from the preserved source archive.

    The release package keeps the 31 MB source archive as provenance, while
    this helper avoids requiring a working-tree extraction of the much larger
    merged CSV.  The returned frame follows the same validation contract as
    :func:`load_oedi_merged`.
    """
    archive = Path(zip_path)
    if not archive.is_file():
        raise FileNotFoundError(archive)
    with ZipFile(archive) as bundle:
        try:
            with bundle.open(internal_path) as handle:
                frame = pd.read_csv(handle)
        except KeyError as exc:
            raise FileNotFoundError(
                f"OEDI archive member not found: {internal_path}"
            ) from exc
    missing = sorted(OEDI_MERGED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"OEDI merged file missing columns: {missing}")
    # Reuse the exact dtype and timestamp checks without writing a temporary
    # extracted file to disk.
    out = frame.copy()
    out["start_time"] = pd.to_datetime(out["start_time"], errors="coerce")
    if out["start_time"].isna().any():
        raise ValueError("OEDI start_time contains invalid timestamps")
    for column in ("duration", "min_customers", "max_customers", "mean_customers"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
        if out[column].isna().any() or (out[column] < 0).any():
            raise ValueError(f"OEDI column {column!r} contains invalid values")
    out["fips"] = out["fips"].astype(str).str.zfill(5)
    return out


def load_oedi_event_correlated_from_zip(
    zip_path: str | Path,
    *,
    year: int,
    lag_hours: int | None = None,
) -> pd.DataFrame:
    """Load the event-correlated OEDI table for ``year`` from the ZIP.

    ``lag_hours`` selects the published 8-hour or 24-hour lag variant.  The
    default is the contemporaneous event correlation table, which includes the
    event type and event restoration timestamp needed for replay evidence.
    """
    if int(year) < 2014 or int(year) > 2023:
        raise ValueError("OEDI R1 event-correlated years are 2014..2023")
    suffix = "" if lag_hours is None else f"_{int(lag_hours)}_hours_lag"
    internal = f"Outage_Dataset/eaglei_outages_with_events_{int(year)}{suffix}.csv"
    archive = Path(zip_path)
    with ZipFile(archive) as bundle:
        try:
            with bundle.open(internal) as handle:
                frame = pd.read_csv(handle)
        except KeyError as exc:
            raise FileNotFoundError(f"OEDI archive member not found: {internal}") from exc
    required = {
        "event_id", "state_event", "Datetime Event Began", "Datetime Restoration",
        "Event Type", *OEDI_MERGED_COLUMNS,
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"OEDI event-correlated file missing columns: {missing}")
    out = frame.copy()
    for column in ("Datetime Event Began", "Datetime Restoration", "start_time", "end_time"):
        if column in out:
            out[column] = pd.to_datetime(out[column], errors="coerce")
            if out[column].isna().any():
                raise ValueError(f"OEDI column {column!r} contains invalid timestamps")
    for column in ("duration", "min_customers", "max_customers", "mean_customers"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
        if out[column].isna().any() or (out[column] < 0).any():
            raise ValueError(f"OEDI column {column!r} contains invalid values")
    out["fips"] = out["fips"].astype(str).str.zfill(5)
    return out


def filter_oedi_events(
    frame: pd.DataFrame,
    *,
    state: str | None = None,
    county: str | None = None,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Filter event rows without changing source columns."""
    out = frame.copy()
    if state is not None:
        out = out[out["state"].astype(str).str.casefold() == state.casefold()]
    if county is not None:
        out = out[out["county"].astype(str).str.casefold() == county.casefold()]
    if start is not None:
        out = out[out["start_time"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["start_time"] < pd.Timestamp(end)]
    return out.reset_index(drop=True)


def outage_fraction_proxy(max_customers: float, *, reference_customers: float) -> float:
    """Return a capped regional proxy; the denominator must be explicit."""
    if reference_customers <= 0:
        raise ValueError("reference_customers must be positive")
    if max_customers < 0:
        raise ValueError("max_customers must be non-negative")
    return float(np.clip(max_customers / reference_customers, 0.0, 1.0))


def map_outage_to_nodes(
    model: GridModel,
    *,
    outage_fraction: float,
    event_id: str,
    source_id: str,
    duration_h: float | None = None,
    mapping_method: str = "regional_statistical_mapping",
) -> pd.DataFrame:
    """Apply a regional outage fraction to study nodes without inventing branches."""
    if not 0.0 <= outage_fraction <= 1.0:
        raise ValueError("outage_fraction must be in [0, 1]")
    if not event_id.strip() or not source_id.strip():
        raise ValueError("event_id and source_id must be non-empty")
    nodes = model.nodes.reset_index().copy()
    total_load = float(nodes["base_load_kw"].sum())
    if total_load <= 0:
        raise ValueError("model must contain positive base load")
    nodes["node_weight"] = nodes["base_load_kw"] / total_load
    nodes["outage_fraction"] = float(outage_fraction)
    nodes["estimated_unserved_kw"] = nodes["base_load_kw"] * outage_fraction
    nodes["estimated_served_kw"] = nodes["base_load_kw"] - nodes["estimated_unserved_kw"]
    nodes["duration_h"] = np.nan if duration_h is None else float(duration_h)
    nodes["event_id"] = event_id
    nodes["source_id"] = source_id
    nodes["mapping_method"] = mapping_method
    nodes["data_class"] = "E_external_aggregate"
    return nodes[[
        "node_id", "label", "base_load_kw", "node_weight", "outage_fraction",
        "estimated_unserved_kw", "estimated_served_kw", "duration_h", "event_id",
        "source_id", "mapping_method", "data_class",
    ]].round(6)


def map_oedi_event_row(
    model: GridModel,
    event_row: pd.Series,
    *,
    reference_customers: float,
    source_id: str = "OEDI-EAGLEI-MERGED",
) -> pd.DataFrame:
    """Map one validated OEDI merged event row to the study nodes."""
    required = {"state", "county", "start_time", "duration", "max_customers"}
    missing = sorted(required.difference(event_row.index))
    if missing:
        raise ValueError(f"event row missing columns: {missing}")
    event_id = (
        f"{source_id}:{event_row['state']}:{event_row['county']}:"
        f"{pd.Timestamp(event_row['start_time']).isoformat()}"
    )
    fraction = outage_fraction_proxy(
        float(event_row["max_customers"]), reference_customers=reference_customers
    )
    return map_outage_to_nodes(
        model,
        outage_fraction=fraction,
        event_id=event_id,
        source_id=source_id,
        duration_h=float(event_row["duration"]),
    )
