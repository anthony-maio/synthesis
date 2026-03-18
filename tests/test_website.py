"""Static website package checks."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "website"


def test_website_core_files_exist() -> None:
    """The website package should include the files needed for static hosting."""
    assert (WEBSITE / "index.html").exists()
    assert (WEBSITE / "style.css").exists()
    assert (WEBSITE / "app.js").exists()
    assert (WEBSITE / "404.html").exists()
    assert (WEBSITE / "favicon.svg").exists()


def test_index_references_static_assets() -> None:
    """The main document should reference the core assets."""
    html = (WEBSITE / "index.html").read_text(encoding="utf-8")

    assert 'href="style.css"' in html
    assert 'src="app.js"' in html
    assert 'href="favicon.svg"' in html


def test_reveal_system_is_wired() -> None:
    """Reveal classes should have both CSS and JS behavior."""
    css = (WEBSITE / "style.css").read_text(encoding="utf-8")
    js = (WEBSITE / "app.js").read_text(encoding="utf-8")

    assert ".reveal" in css
    assert ".is-visible" in css
    assert "IntersectionObserver" in js
