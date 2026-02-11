#!/usr/bin/env python3
# Copyright (c) 2026 Robin Mordasiewicz. MIT License.

"""Generate Scalar API viewer pages and Starlight MDX wrappers.

Reads docs/specifications/api/index.json and generates:
  - docs/specifications/api/viewer/{domain}.html  (standalone Scalar viewers)
  - docs/api-reference/{domain}.mdx               (Starlight iframe wrappers)
  - docs/api-reference/index.mdx                  (catalog landing page)

Usage:
    python -m scripts.generate_api_viewer
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

# Pinned Scalar CDN version for reproducible builds
SCALAR_CDN_VERSION = "1.44.16"
SCALAR_CDN_URL = (
    f"https://cdn.jsdelivr.net/npm/@scalar/api-reference@{SCALAR_CDN_VERSION}"
)

SPEC_DIR = Path("docs/specifications/api")
VIEWER_DIR = SPEC_DIR / "viewer"
MDX_DIR = Path("docs/api-reference")
INDEX_JSON = SPEC_DIR / "index.json"


def generate_viewer_html(domain: str, title: str) -> str:
    """Generate a standalone Scalar API viewer HTML page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} - API Reference</title>
  <style>
    body {{ margin: 0; padding: 0; }}
  </style>
</head>
<body>
  <div id="app"></div>
  <script src="{SCALAR_CDN_URL}"></script>
  <script>
    Scalar.createApiReference('#app', {{
      url: '../{domain}.json',
      theme: 'kepler',
      darkMode: true,
      defaultOpenAllTags: false,
      hideDownloadButton: false,
    }});
  </script>
</body>
</html>
"""


def generate_domain_mdx(domain: str, title: str, description: str) -> str:
    """Generate a Starlight MDX wrapper page for a domain viewer."""
    viewer_path = f"/specifications/api/viewer/{domain}.html"
    spec_path = f"/specifications/api/{domain}.json"

    return f"""---
title: "{title}"
description: "{description}"
sidebar:
  badge:
    text: API
    variant: note
---

import {{ LinkCard }} from '@astrojs/starlight/components';
import ScalarViewer from '@components/ScalarApiViewerWrapper.astro';

<div style="margin-bottom: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
  <LinkCard title="Back to API Catalog" href="/api-reference/" />
  <LinkCard title="Full Screen" href="{viewer_path}" />
  <LinkCard title="Download Spec" href="{spec_path}" />
</div>

<ScalarViewer specUrl="{spec_path}" title="{title}" />
"""


def generate_catalog_mdx(
    specs: list[dict],
) -> str:
    """Generate the API Reference catalog landing page."""
    # Group specs by category
    categories: dict[str, list[dict]] = defaultdict(list)
    for spec in specs:
        cat = spec.get("x-f5xc-category", "Other")
        categories[cat].append(spec)

    # Desired category display order
    category_order = [
        "Security",
        "Networking",
        "Infrastructure",
        "Platform",
        "Operations",
        "AI",
        "Other",
    ]

    cards_sections = []
    for cat in category_order:
        if cat not in categories:
            continue
        domain_list = sorted(categories[cat], key=lambda s: s["title"])

        cards = []
        for spec in domain_list:
            domain = spec["domain"]
            title = spec["title"]
            icon = spec.get("x-f5xc-icon", "📄")
            short_desc = spec.get("x-f5xc-description-short", "")
            complexity = spec.get("x-f5xc-complexity", "")
            path_count = spec.get("path_count", 0)
            schema_count = spec.get("schema_count", 0)

            badge = ""
            if spec.get("x-f5xc-is-preview"):
                badge = " (Preview)"

            description_line = short_desc if short_desc else title
            stats_line = f"{path_count} paths, {schema_count} schemas"
            if complexity:
                stats_line += f", {complexity}"

            cards.append(
                f'  <LinkCard title="{icon} {title}{badge}" '
                f'description="{description_line} — {stats_line}" '
                f'href="/api-reference/{domain}/" />',
            )

        cards_block = "\n".join(cards)
        cards_sections.append(f"### {cat}\n\n<CardGrid>\n{cards_block}\n</CardGrid>")

    all_sections = "\n\n".join(cards_sections)

    return f"""---
title: API Reference
description: Interactive API documentation for F5 Distributed Cloud services
sidebar:
  order: 0
---

import {{ CardGrid, LinkCard }} from '@astrojs/starlight/components';

Explore the F5 Distributed Cloud API with interactive documentation powered by
[Scalar](https://scalar.com). Each domain includes a **Try It** console for
testing API calls directly from your browser.

{all_sections}
"""


def main() -> int:
    """Generate all viewer and MDX files."""
    if not INDEX_JSON.exists():
        print(f"Error: {INDEX_JSON} not found. Run 'make pipeline' first.")
        return 1

    with INDEX_JSON.open() as f:
        index = json.load(f)

    specs = index.get("specifications", [])
    if not specs:
        print("Error: No specifications found in index.json")
        return 1

    # Create output directories
    VIEWER_DIR.mkdir(parents=True, exist_ok=True)
    MDX_DIR.mkdir(parents=True, exist_ok=True)

    # Remove stale files from previous runs (domains may be added/removed)
    valid_domains = {spec["domain"] for spec in specs}
    for stale in VIEWER_DIR.glob("*.html"):
        if stale.stem not in valid_domains:
            stale.unlink()
    for stale in MDX_DIR.glob("*.mdx"):
        if stale.stem != "index" and stale.stem not in valid_domains:
            stale.unlink()

    # Generate standalone HTML viewers + MDX wrappers per domain
    for spec in specs:
        domain = spec["domain"]
        title = spec["title"]
        description = spec.get("x-f5xc-description-short", title)

        # Standalone Scalar viewer
        html_path = VIEWER_DIR / f"{domain}.html"
        html_path.write_text(generate_viewer_html(domain, title))

        # Starlight MDX wrapper
        mdx_path = MDX_DIR / f"{domain}.mdx"
        mdx_path.write_text(generate_domain_mdx(domain, title, description))

    # Generate catalog landing page
    catalog_path = MDX_DIR / "index.mdx"
    catalog_path.write_text(generate_catalog_mdx(specs))

    print(f"Generated {len(specs)} viewer pages in {VIEWER_DIR}")
    print(f"Generated {len(specs)} MDX wrappers + catalog in {MDX_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
