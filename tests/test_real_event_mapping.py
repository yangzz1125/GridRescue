import pandas as pd
import pytest

from gridrescue.network import build_ieee33
from gridrescue.real_event_mapping import (
    filter_oedi_events,
    load_oedi_csv_from_zip,
    load_oedi_event_correlated_from_zip,
    load_oedi_merged,
    map_oedi_event_row,
    map_outage_to_nodes,
    outage_fraction_proxy,
)


def test_oedi_zip_readers(tmp_path):
    archive = tmp_path / "oedi.zip"
    from zipfile import ZipFile, ZIP_DEFLATED

    frame = pd.DataFrame([{
        "fips": 1001, "state": "Alabama", "county": "Autauga",
        "start_time": "2023-01-03 22:15:00", "duration": 0.75,
        "min_customers": 245, "max_customers": 275, "mean_customers": 257,
    }])
    event = frame.assign(
        event_id="Alabama-0", state_event="Alabama",
        **{
            "Datetime Event Began": "2023-01-03 00:00:00",
            "Datetime Restoration": "2023-01-03 04:00:00",
            "Event Type": "Severe Weather",
            "end_time": "2023-01-03 23:00:00",
        },
    )
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        bundle.writestr("Outage_Dataset/eaglei_outages_2023_merged.csv", frame.to_csv(index=False))
        bundle.writestr("Outage_Dataset/eaglei_outages_with_events_2023.csv", event.to_csv(index=False))
    assert len(load_oedi_csv_from_zip(archive)) == 1
    loaded = load_oedi_event_correlated_from_zip(archive, year=2023)
    assert loaded.iloc[0]["event_id"] == "Alabama-0"
    assert loaded.iloc[0]["Datetime Restoration"].hour == 4


def test_oedi_loader_and_filter(tmp_path):
    path = tmp_path / "oedi.csv"
    pd.DataFrame(
        [{
            "fips": 1001,
            "state": "Alabama",
            "county": "Autauga",
            "start_time": "2023-01-03 22:15:00",
            "duration": 0.75,
            "min_customers": 245,
            "max_customers": 275,
            "mean_customers": 257,
        }]
    ).to_csv(path, index=False)
    frame = load_oedi_merged(path)
    selected = filter_oedi_events(frame, state="alabama")
    assert selected.iloc[0]["fips"] == "01001"
    assert selected.iloc[0]["duration"] == 0.75


def test_mapping_preserves_aggregate_unserved_load():
    model = build_ieee33()
    mapped = map_outage_to_nodes(
        model,
        outage_fraction=0.2,
        event_id="TEST-EVENT",
        source_id="TEST-SOURCE",
        duration_h=4.5,
    )
    assert len(mapped) == 33
    assert mapped["estimated_unserved_kw"].sum() == pytest.approx(
        model.nodes["base_load_kw"].sum() * 0.2
    )
    assert mapped["mapping_method"].eq("regional_statistical_mapping").all()
    assert mapped["data_class"].eq("E_external_aggregate").all()


def test_oedi_event_row_mapping_is_explicit_proxy():
    model = build_ieee33()
    row = pd.Series({
        "state": "Alabama",
        "county": "Autauga",
        "start_time": pd.Timestamp("2023-01-03 22:15:00"),
        "duration": 0.75,
        "max_customers": 275,
    })
    assert outage_fraction_proxy(275, reference_customers=1000) == pytest.approx(0.275)
    mapped = map_oedi_event_row(model, row, reference_customers=1000)
    assert mapped["outage_fraction"].iloc[0] == pytest.approx(0.275)
    assert mapped["duration_h"].iloc[0] == pytest.approx(0.75)
    assert "OEDI-EAGLEI-MERGED:Alabama:Autauga" in mapped["event_id"].iloc[0]


def test_invalid_proxy_inputs_are_rejected():
    with pytest.raises(ValueError):
        outage_fraction_proxy(10, reference_customers=0)
    with pytest.raises(ValueError):
        map_outage_to_nodes(
            build_ieee33(), outage_fraction=1.1, event_id="x", source_id="y"
        )
