"""Capture full-page screenshots of every dashboard page with Playwright.

Usage (from the project root, with the app already running):
    .venv/bin/python -m streamlit run dashboard/streamlit/app.py \
        --server.headless true --server.port 8599 &
    .venv/bin/python dashboard/streamlit/capture_screenshots.py --base-url http://localhost:8599

Writes docs/images/dashboard_<page>.png. Requires `pip install playwright` and
`python -m playwright install chromium`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "docs" / "images"

# (url path registered by st.navigation, output slug, number of plotly charts expected)
PAGES: list[tuple[str, str, int]] = [
    ("", "overview", 2),
    ("operations", "operations", 6),
    ("outcomes", "outcomes", 6),
    ("clinical", "clinical", 4),
    ("data_quality", "data_quality", 3),
    ("sql_explorer", "sql_explorer", 0),
]


def wait_for_render(page: Page, expected_charts: int, timeout_ms: int = 45_000) -> None:
    page.wait_for_load_state("networkidle", timeout=timeout_ms)
    page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=timeout_ms)
    # Streamlit shows a "running" status widget while the script executes.
    page.wait_for_function(
        "() => !document.querySelector('[data-testid=\"stStatusWidget\"]')",
        timeout=timeout_ms,
    )
    if expected_charts:
        page.wait_for_function(
            f"() => document.querySelectorAll('.js-plotly-plot .main-svg').length >= "
            f"{expected_charts}",
            timeout=timeout_ms,
        )
    page.wait_for_timeout(3000)  # let Plotly finish layout transitions and fonts settle


def capture(base_url: str, width: int, height: int) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": height},
                                      device_scale_factor=1)
        page = context.new_page()
        for url_path, slug, n_charts in PAGES:
            page.goto(f"{base_url.rstrip('/')}/{url_path}", wait_until="domcontentloaded")
            wait_for_render(page, n_charts)
            errors = page.locator('[data-testid="stException"]').count()
            if errors:
                print(f"WARNING: {slug} shows {errors} exception block(s)", file=sys.stderr)
            out = OUT_DIR / f"dashboard_{slug}.png"
            # Streamlit scrolls inside its main container, not the document, so grow the
            # viewport to the content height before taking the full-page screenshot.
            content_h = page.evaluate(
                "() => { const m = document.querySelector('[data-testid=\"stMain\"]');"
                " return m ? m.scrollHeight : document.body.scrollHeight; }"
            )
            page.set_viewport_size({"width": width, "height": max(height, int(content_h))})
            page.wait_for_timeout(2500)  # Plotly re-lays out on resize
            page.screenshot(path=str(out), full_page=True)
            page.set_viewport_size({"width": width, "height": height})
            written.append(out)
            print(f"saved {out.relative_to(PROJECT_ROOT)}")
        browser.close()
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8599")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    args = parser.parse_args()
    capture(args.base_url, args.width, args.height)


if __name__ == "__main__":
    main()
