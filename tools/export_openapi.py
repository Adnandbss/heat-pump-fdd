"""Dump OpenAPI JSON for `npm run gen:api`. Importing create_app does not load the joblib."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.main import create_app

OUT = ROOT / "web" / "openapi.json"


def main() -> None:
    spec = create_app().openapi()
    OUT.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
