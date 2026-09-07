from gridrescue.facts import FACTS, validate_text


def test_canonical_facts_are_frozen():
    assert FACTS.freeze_date == "2026-08-22"
    assert FACTS.tests_passed == 46
    assert FACTS.mrv_bundle_count == 3
    assert FACTS.mrv_checked_files == 17
    assert FACTS.unit == "kgCO2"
    assert FACTS.same_service_pass is False


def test_claim_guard_rejects_strict_same_service_wording():
    errors = validate_text("结果证明严格同服务减排。")
    assert errors


def test_claim_guard_rejects_co2e_alias():
    assert validate_text("排放为 10 kgCO2e")
