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
        features="23-col",
    )
    pct = f"{acc * 100:.1f}"
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert pct in text, f"README does not publish the logged hold-out accuracy {pct} %"
    assert "hold-out" in text.lower() or "holdout" in text.lower()


def test_readme_results_percentages_are_logged():
    """Every xx.x % in README Results must match a logged value.

    Presence of one 89.3 left the previous test green after a second 89.3
    was edited. A realistic edit that must go red: change either table
    accuracy without updating results.csv.
    """
    from tools.results import get

    text = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"^## Results\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, "README has no ## Results section"
    section = match.group(1)
    cited_pct = {p.replace(",", ".") for p in re.findall(r"(\d+[.,]\d+)\s*%", section)}
    cited_dec = set()
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        for cell in line.split("|"):
            raw = cell.strip().replace(",", ".").strip("*")
            if re.fullmatch(r"0\.\d+", raw):
                cited_dec.add(f"{float(raw):.3f}")
    logged_pct = set()
    logged_dec = set()
    for row in get():
        value = float(row["value"])
        logged_pct.add(f"{value * 100:.1f}")
        logged_dec.add(f"{value:.3f}")
        for a, b in re.findall(r"\[(\d+\.\d+),\s*(\d+\.\d+)\]", row.get("note") or ""):
            lo, hi = float(a), float(b)
            scale = 100.0 if lo <= 1.0 else 1.0
            logged_pct.add(f"{lo * scale:.1f}")
            logged_pct.add(f"{hi * scale:.1f}")
            logged_dec.add(f"{lo:.3f}")
            logged_dec.add(f"{hi:.3f}")
    missing_pct = sorted(cited_pct - logged_pct)
    missing_dec = sorted(cited_dec - logged_dec)
    assert not missing_pct, (
        f"README Results cites {missing_pct} % with no matching row in results.csv"
    )
    assert not missing_dec, (
        f"README Results tables cite {missing_dec} with no matching row in results.csv"
    )


def test_dossier_x0_matches_results_csv():
    from tools.results import value

    acc = value(
        experiment="X0",
        protocol="holdout-test",
        metric="accuracy",
        model="random-forest",
        label="__global__",
        features="23-col",
    )
    french = f"{acc * 100:.1f}".replace(".", ",")
    dossier = ROOT / "docs" / "DOSSIER.md"
    if not dossier.exists():
        pytest.skip("DOSSIER.md absent")
    text = dossier.read_text(encoding="utf-8")
    assert french in text, f"DOSSIER.md does not publish the logged hold-out accuracy {french} %"


def test_web_tsx_has_no_hardcoded_result_percentages():
    """FRONT_PLAN §1: result figures live in results.csv, never in TSX."""
    pattern = re.compile(r"[0-9]+\.[0-9]+\s*%")
    offenders = []
    src = ROOT / "web" / "src"
    if not src.exists():
        pytest.skip("web/src absent")
    for path in sorted(src.rglob("*.tsx")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{line_no}: {line.strip()}")
    assert not offenders, "hardcoded result percentages in TSX:\n" + "\n".join(offenders)
