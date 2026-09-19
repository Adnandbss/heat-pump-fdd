"""Domain errors. HTTP status codes live in the handlers, not the routes."""


class ArtifactMissing(Exception):
    """A required on-disk artefact is absent (model, dataset, comparison table)."""

    def __init__(self, name: str, detail: str | None = None):
        self.name = name
        self.detail = detail or f"Missing {name}. Run main_analysis.py first."
        super().__init__(self.detail)


class UnprocessableInput(Exception):
    """Request names or values the domain cannot accept (HTTP 422)."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class UnknownFeature(UnprocessableInput):
    def __init__(self, name: str, kind: str = "feature"):
        super().__init__(f"Unknown {kind}: {name}")
        self.name = name
        self.kind = kind


class InvalidFeatureVector(UnprocessableInput):
    """The feature payload is the wrong shape or is missing a trained column."""
