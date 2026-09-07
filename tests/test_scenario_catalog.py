from gridrescue.scenario_catalog import build_catalog, catalog_manifest


def test_catalog_has_36_replayable_rows():
    rows = build_catalog()
    assert len(rows) == 36
    assert len({row.scenario_id for row in rows}) == 36
    assert len({row.payload_sha256 for row in rows}) == 36
    assert {row.disaster for row in rows} == {"暴雨内涝", "台风", "极端高温"}
    assert {row.intensity for row in rows} == {"low", "medium", "high"}
    assert {row.replicate for row in rows} == {1, 2, 3, 4}


def test_catalog_is_deterministic_and_manifest_is_hashed():
    first = build_catalog()
    second = build_catalog()
    assert [row.payload_sha256 for row in first] == [row.payload_sha256 for row in second]
    manifest = catalog_manifest(first)
    assert manifest["count"] == 36
    assert manifest["freeze_date"] == "2026-08-22"
    assert manifest["data_class"] == "E"


def test_catalog_row_can_replay_through_existing_scenario_type():
    row = build_catalog()[0]
    scenario = row.to_disaster_scenario()
    assert scenario.name == row.scenario_id
    assert scenario.failed_branch_ids == tuple(row.parameters["failed_branch_ids"])
