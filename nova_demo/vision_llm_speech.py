"""Launch the continuous vision, LLM, and speech demo."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    nova_testing_dir = Path(__file__).resolve().parents[1]
    script_path = nova_testing_dir / "main.py"

    os.chdir(nova_testing_dir)
    sys.path.insert(0, str(nova_testing_dir))
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    main()
