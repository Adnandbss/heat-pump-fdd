"""FaultType, the generated mix, and metadata.json must name the same classes.

Two ghost classes (overcharge never generated, valve leak never modelled)
survived because nothing compared the three lists.
"""

from __future__ import annotations

import json

import pandas as pd

from api.schemas import FaultLabel
from src.studies.synthetic.generator import FaultDataGenerator, FaultType
from src.studies.synthetic.paths import DATASET_PATH, METADATA_PATH
from src.studies.synthetic.taxonomy import FAULT_PARAM_MAP


def test_overcharge_injection_does_not_touch_fouling():
    gen = FaultDataGenerator(random_seed=0)
    params = gen._apply_fault(FaultType.REFRIGERANT_OVERCHARGE, 0.20)
    assert params["refrigerant_charge"] == 1.10
    assert params["condenser_fouling"] == 0.0
    assert params["evaporator_fouling"] == 0.0


def test_valve_leak_is_gone():
    assert "COMPRESSOR_VALVE_LEAK" not in FaultType.__members__
    assert "Compressor_Valve_Leak" not in {ft.value for ft in FaultType}
    assert "Compressor_Valve_Leak" not in FAULT_PARAM_MAP


def test_faulttype_matches_generated_dataset_and_metadata():
    declared = {ft.value for ft in FaultType}
    assert len(declared) == 7

    assert DATASET_PATH.exists(), "run main_analysis.py to ship the dataset"
    generated = set(pd.read_csv(DATASET_PATH)["fault_type"].unique())

    meta = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    shipped = set(meta["classes"])

    assert declared == generated == shipped, (
        f"FaultType={sorted(declared)}  dataset={sorted(generated)}  "
        f"metadata={sorted(shipped)}"
    )


def test_api_labels_match_faulttype():
    assert {e.value for e in FaultLabel} == {ft.value for ft in FaultType}


def test_demo_map_covers_every_faulttype():
    assert set(FAULT_PARAM_MAP) == {ft.value for ft in FaultType}


def test_default_generator_emits_every_declared_class():
    gen = FaultDataGenerator(random_seed=0)
    df = gen.generate_dataset(n_samples=70, show_progress=False)
    assert set(df["fault_type"]) == {ft.value for ft in FaultType}
