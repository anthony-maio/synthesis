from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC_FILES = ["index.html", "style.css", "app.js", "404.html", "favicon.svg", "README.md"]


def test_website_sync_script_reports_in_sync_repo(tmp_path: Path) -> None:
    dest = tmp_path / "synthesis-web"
    dest.mkdir()
    source_root = ROOT / "website"
    for name in SYNC_FILES:
        (dest / name).write_bytes((source_root / name).read_bytes())

    result = subprocess.run(
        [
            sys.executable,
            "scripts/sync_website.py",
            "--source",
            "website",
            "--dest",
            str(dest),
            "--check",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "in sync" in result.stdout
