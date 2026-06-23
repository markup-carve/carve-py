"""Minimal proof-of-concept MkDocs plugin for Carve (`.crv` / `.carve`) pages.

This is a thin BasePlugin that intercepts `.crv` / `.carve` source pages and
converts them to HTML with `carve.to_html` before MkDocs renders them. It is a
demonstration of how cheaply python-carve unblocks the MkDocs ecosystem, not a
production plugin.

To use in a real MkDocs site, register the entry point in pyproject.toml:

    [project.entry-points."mkdocs.plugins"]
    carve = "mkdocs_carve:CarvePlugin"

then add `plugins: [carve]` to mkdocs.yml.
"""

from __future__ import annotations

import carve

CARVE_SUFFIXES = (".crv", ".carve")


def convert_carve(source: str, extensions=None) -> str:
    """Convert Carve source to an HTML fragment."""
    return carve.to_html(source, extensions=extensions)


try:
    from mkdocs.plugins import BasePlugin
    from mkdocs.structure.files import Files

    class CarvePlugin(BasePlugin):
        """Render `.crv` / `.carve` pages through carve-rs via python-carve.

        Two hooks:

        - `on_files`: MkDocs only treats `.md` files as documentation pages.
          We patch each Carve File so `is_documentation_page()` returns True
          and it gets a `.html` destination, so MkDocs builds it as a page.
        - `on_page_markdown`: MkDocs hands us the raw page text; for a Carve
          source we convert it to an HTML fragment. Markdown passes raw HTML
          through, so the converted page renders as-is.
        """

        def on_files(self, files, *, config):
            import os

            site_dir = config["site_dir"]
            for f in files:
                src_path = getattr(f, "src_path", "") or ""
                if src_path.endswith(CARVE_SUFFIXES):
                    # Make MkDocs build this as a documentation page.
                    f.is_documentation_page = lambda: True
                    base = src_path
                    for suffix in CARVE_SUFFIXES:
                        if base.endswith(suffix):
                            base = base[: -len(suffix)]
                            break
                    # index.crv -> index.html; other.crv -> other/index.html
                    if os.path.basename(base) == "index":
                        dest = base + ".html"
                    else:
                        dest = os.path.join(base, "index.html")
                    f.dest_path = dest
                    f.abs_dest_path = os.path.normpath(os.path.join(site_dir, dest))
                    f.url = dest.replace(os.sep, "/").replace("index.html", "")
                    if not f.url:
                        f.url = "."
            return files

        def on_page_markdown(self, markdown, *, page, config, files):
            src_path = getattr(page.file, "src_path", "") or ""
            if src_path.endswith(CARVE_SUFFIXES):
                return convert_carve(markdown)
            return markdown

except ImportError:  # mkdocs not installed; the converter above still works.
    BasePlugin = None
    CarvePlugin = None
