"""Synthetic-study taxonomy stays aligned with the demo map."""

from src.studies.synthetic.taxonomy import FAULT_PARAM_MAP, SCENARIOS


def test_scenarios_cover_every_mapped_fault():
    mapped = set(FAULT_PARAM_MAP)
    titled = {spec["fault_type"] for spec in SCENARIOS.values()}
    assert mapped == titled
    assert len(SCENARIOS) == 6


def test_scenario_params_match_the_fault_map():
    for spec in SCENARIOS.values():
        assert spec["params"] == FAULT_PARAM_MAP[spec["fault_type"]]
        assert spec["description"]


def test_features_does_not_own_scenarios():
    import src.fdd.features as features

    assert not hasattr(features, "SCENARIOS")
