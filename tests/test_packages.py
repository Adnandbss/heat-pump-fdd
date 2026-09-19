"""Layer packages exist before the modules move into them."""


def test_physics_fdd_and_studies_packages_import():
    import src.fdd
    import src.physics
    import src.studies
    import src.studies.synthetic


def test_moved_modules_import_from_their_layers():
    from src.fdd.features import FEATURE_COLUMNS
    from src.fdd.ml_models import FDDClassifier
    from src.physics.simulator import HeatPumpSimulator
    from src.studies.synthetic.generator import FaultDataGenerator

    assert len(FEATURE_COLUMNS) == 23
    assert "pressure_ratio" not in FEATURE_COLUMNS
    assert FDDClassifier is not None
    assert HeatPumpSimulator is not None
    assert FaultDataGenerator is not None

