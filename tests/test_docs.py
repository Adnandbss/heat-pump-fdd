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

    section = _results_section()
    cited = {p.replace(",", ".") for p in re.findall(r"(\d+[.,]\d+)\s*%", section)}
    logged = set()
    for row in get():
        logged.add(f"{float(row['value']) * 100:.1f}")
        for a, b in re.findall(r"\[(\d+\.\d+),\s*(\d+\.\d+)\]", row.get("note") or ""):
            lo, hi = float(a), float(b)
            scale = 100.0 if lo <= 1.0 else 1.0
            logged.add(f"{lo * scale:.1f}")
            logged.add(f"{hi * scale:.1f}")
    missing = sorted(cited - logged)
    assert not missing, (
        f"README Results cites {missing} % with no matching row in results.csv"
    )


def _results_section() -> str:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"^## Results\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, "README has no ## Results section"
    return match.group(1)


_SOURCE_TAG = re.compile(r"<!--\s*results-source:\s*(.+?)\s*-->")
_DECIMAL = re.compile(r"0\.\d+")


def _tables_with_sources(section: str):
    """Yield (source_pairs, header_cells, body_lines) for each Results table."""
    pending: list[tuple[str, str]] = []
    block: list[str] = []
    for line in section.splitlines():
        tag = _SOURCE_TAG.search(line)
        if tag:
            pending = [tuple(item.strip().split("/", 1)) for item in tag.group(1).split(",")]
            continue
        if line.strip().startswith("|"):
            block.append(line)
            continue
        if block:
            yield pending, block
            pending, block = [], []
    if block:
        yield pending, block


def _column_metric(header: str) -> str | None:
    lowered = header.lower()
    if "f1" in lowered:
        return "f1"
    if "accuracy" in lowered:
        return "accuracy"
    return None


def test_readme_results_decimals_name_their_source():
    """Each Results table declares which (experiment, protocol) it reads.

    Matching on the bare value is not a guard: results.csv holds 656 rows and
    only 327 distinct values at three decimals, so a number drawn at random in
    [0.25, 0.99] lands on some unrelated row 42 % of the time. That is how the
    README's calibration table passed while citing figures that were never
    logged, and how a Val F1 of 0.905 was covered by an accuracy of 0.905333.

    A cell that no logged row backs must carry a dagger and say so in print.
    """
    from tools.results import get

    section = _results_section()
    rows = list(get())
    offenders: list[str] = []
    checked = 0

    for sources, block in _tables_with_sources(section):
        header = [c.strip() for c in block[0].split("|")]
        assert sources, f"Results table has no `<!-- results-source: ... -->` tag: {block[0]}"
        allowed = [
            r
            for r in rows
            if any(r["experiment"] == exp and r["protocol"] == proto for exp, proto in sources)
        ]
        assert allowed, f"no results.csv row matches {sources}"
        for line in block[2:]:
            cells = [c.strip() for c in line.split("|")]
            for index, cell in enumerate(cells):
                found = _DECIMAL.search(cell.replace(",", "."))
                if not found:
                    continue
                metric = _column_metric(header[index]) if index < len(header) else None
                if metric is None:
                    continue
                checked += 1
                if "†" in cell:
                    continue
                value = float(found.group())
                if not any(
                    r["metric"] == metric and round(float(r["value"]), 3) == round(value, 3)
                    for r in allowed
                ):
                    offenders.append(
                        f"{cells[1] if len(cells) > 1 else line.strip()!r}: "
                        f"{header[index]} = {value} has no {metric} row in {sources}"
                    )

    assert checked, "no Results table cell was checked -- the parser found nothing"
    assert not offenders, (
        "README Results cites figures that results.csv does not back.\n"
        "Log the measurement, or mark the cell with † and footnote it:\n  "
        + "\n  ".join(offenders)
    )
    if "†" in section:
        assert re.search(r"^†", section, re.M), (
            "a Results cell is marked † but the section defines no † footnote"
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
