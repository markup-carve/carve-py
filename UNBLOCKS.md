# What python-carve unblocks

With a working `import carve` that exposes `to_html` (plus `to_markdown`,
`to_plain_text`, `to_ansi`) backed by the carve-rs engine, the whole Python
docs / data ecosystem can render Carve. Below is each integration, what it
takes, and how hard it is now.

Difficulty scale: Trivial < Easy < Moderate < Involved.

## MkDocs plugin - Easy (PROVEN here)

A `mkdocs.plugins.BasePlugin` that:

- registers via the `mkdocs.plugins` entry point,
- in `on_files`, marks `.crv` files as documentation pages and
  gives them an `.html` destination,
- in `on_page_markdown`, calls `carve.to_html(source)` and returns the HTML
  fragment (Markdown passes raw HTML through).

Status: a minimal proof in `mkdocs-proof/` runs a real `mkdocs build` and emits
`index.html` containing the converted Carve heading, bold, list, inline code,
and table. About 40 lines of Python. This is the easiest high-value target and
is the recommended first official package.

## Pelican reader - Easy

Pelican discovers content via `BaseReader` subclasses keyed by file extension.
A `CarveReader(BaseReader)` with `file_extensions = ["crv", "carve"]` and a
`read(path)` that returns `carve.to_html(text), metadata`. Metadata can come
from Carve frontmatter (carve-rs parses frontmatter) or a simple header block.
Roughly one small module plus `readers.append`. No blockers.

## Sphinx - Moderate

Two viable shapes:

1. A `Parser` (docutils/Sphinx `sphinx.parsers.Parser`) registered for `.crv`
   via `source_suffix`, converting to HTML and injecting it as a `raw` node.
   This is the cleanest "Carve pages in a Sphinx project" path.
2. A directive (`.. carve::`) for embedding Carve snippets in `.rst`/MyST.

Moderate because Sphinx wants docutils nodes, not raw HTML strings, for full
cross-referencing / toctree integration. A `raw`-node bridge works immediately;
deep integration (headings feeding the toctree) is more work and would benefit
from exposing the Carve AST or heading list from the binding later.

## Jupyter / nbconvert - Easy to Moderate

- Quick win: a cell magic `%%carve` (an IPython magic) that calls
  `carve.to_html` and returns `IPython.display.HTML`. Trivial, a dozen lines.
- Fuller: an `nbconvert` preprocessor / exporter that treats Carve-typed
  markdown cells as Carve. Moderate, because it touches nbconvert's template
  and cell-type plumbing.

## mdformat-style formatter - Involved

mdformat is a Markdown formatter; a Carve analog would need a *serializer* back
to Carve source, not just HTML. The binding currently exposes HTML / Markdown /
plain / ANSI renderers but no Carve-to-Carve canonical formatter, and round-trip
formatting needs AST access. Involved: it depends on carve-rs growing (and the
binding exposing) a canonical Carve serializer / AST surface. Out of reach with
today's HTML-only surface.

## `python -m carve` CLI - Trivial

A tiny `__main__.py` reading stdin / a file path and printing
`carve.to_html(...)` (with `--markdown` / `--plain` / `--ansi` flags mapping to
the other renderers, and `--extension NAME` repeatable). This mirrors the
carve-rs CLI and is the lowest-effort addition; it just was not in scope for the
binding itself. Trivial.

## Summary table

| Target            | Effort    | Blocker today                          |
|-------------------|-----------|----------------------------------------|
| MkDocs plugin     | Easy      | none (proven)                          |
| Pelican reader    | Easy      | none                                   |
| `python -m carve` | Trivial   | none                                   |
| Jupyter magic     | Easy      | none                                   |
| Sphinx parser     | Moderate  | docutils-node bridge; AST for deep use |
| nbconvert export  | Moderate  | nbconvert template plumbing            |
| mdformat-style    | Involved  | needs a Carve serializer / AST surface |

## What would widen the unblock further

The HTML/Markdown/plain/ANSI renderers cover rendering integrations. The next
binding additions that would unlock the harder targets:

- Expose the parsed AST (or at least the heading list) to Python -> Sphinx
  toctree, tables of contents, link checking.
- Expose `Options` knobs already in carve-rs (mention/tag URL templates,
  emoji map, profiles, `allow_raw_html`, `lowercase_heading_ids`) so security
  profiles and link policies are reachable from Python.
- A canonical Carve serializer (engine-side) -> mdformat-style formatting.
