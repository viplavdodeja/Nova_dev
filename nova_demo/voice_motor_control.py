"""Launch the wake-phrase motor voice control demo."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    nova_testing_dir = Path(__file__).resolve().parents[1]
    script_dir = nova_testing_dir / "motor_voice_control"
    script_path = script_dir / "main.py"

    os.environ.setdefault("NOVA_STT_DEBUG", "1")
    os.chdir(script_dir)
    sys.path.insert(0, str(script_dir))
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    main()
