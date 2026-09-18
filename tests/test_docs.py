"""Guardrails on the documentation.

Two classes of error have already reached `main` in this project: documentation
citing files that no longer exist after a refactor, and documentation stating a
number without the protocol that produced it. Both are cheap to prevent.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = sorted((ROOT / "docs").glob("*.md")) + [ROOT / "README.md"]

# a path cited in backticks, e.g. `src/fdd/features.py` or `outputs/synthetic/`
PATH_RE = re.compile(r"`((?:src|api|web|tests|tools|EDA|docs|outputs|models|data|scripts)/[\w./@-]+)`")

# module paths written with a line number, e.g. `src/fdd/features.py:86`
LINE_SUFFIX = re.compile(r":\d+$")


def _cited_paths(md: Path) -> set[str]:
    text = md.read_text(encoding="utf-8")
    found = set()
    for raw in PATH_RE.findall(text):
        found.add(LINE_SUFFIX.sub("", raw).rstrip("/"))
    return found


@pytest.mark.parametrize("md", DOCS, ids=lambda p: p.name)
def test_documentation_cites_no_dead_path(md):
    """Every repo path named in the docs must exist on disk."""
    if not md.exists():
        pytest.skip(f"{md.name} absent")
    missing = sorted(p for p in _cited_paths(md) if not (ROOT / p).exists())
    assert not missing, (
        f"{md.name} cites paths that do not exist: {missing}\n"
        "A refactor moved them and the documentation was not updated."
    )


def test_lomo_figure_names_its_protocol():
    """0.602 without leave-one-machine-out nearby is the bug this test exists for."""
    readme = ROOT / "README.md"
    if not readme.exists():
        pytest.skip("README absent")
    text = readme.read_text(encoding="utf-8").lower()
    idx = text.find("0.602")
    assert idx >= 0, "README no longer publishes the NIST LOMO figure 0.602"
    window = text[max(0, idx - 500): idx + 500]
    assert "leave-one-machine-out" in window, (
        "0.602 appears in the README without the LOMO protocol in the same passage."
    )


def test_readme_x0_matches_results_csv():
    from tools.results import value

    acc = value(
        experiment="X0",
        protocol="holdout-test",
        metric="accuracy",
        model="random-forest",
        label="__global__",
    )
    pct = f"{acc * 100:.1f}"
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert pct in text, f"README does not publish the logged hold-out accuracy {pct} %"
    assert "hold-out" in text.lower() or "holdout" in text.lower()


def test_dossier_x0_matches_results_csv():
    from tools.results import value

    acc = value(
        experiment="X0",
        protocol="holdout-test",
        metric="accuracy",
        model="random-forest",
        label="__global__",
    )
    french = f"{acc * 100:.1f}".replace(".", ",")
    dossier = ROOT / "docs" / "DOSSIER.md"
    if not dossier.exists():
        pytest.skip("DOSSIER.md absent")
    text = dossier.read_text(encoding="utf-8")
    assert french in text, f"DOSSIER.md does not publish the logged hold-out accuracy {french} %"
