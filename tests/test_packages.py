"""Layer packages exist before the modules move into them."""


def test_physics_fdd_and_studies_packages_import():
    import src.fdd
    import src.physics
    import src.studies
    import src.studies.synthetic
