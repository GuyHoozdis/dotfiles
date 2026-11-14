#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["iterm2"]
# ///
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "share" / "copilot"))
from iterm_notifications.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
