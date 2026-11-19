# Carve 0.2 Python guide

This branch uses the unreleased Carve 0.2 engine (the `carve-lang` crate from
carve-rs `next2`, imported as `carve`) at the git revision in `Cargo.lock`. Its Python functions return dictionaries with the same camelCase
keys as the public Rust JSON boundary. The [type stub](../carve.pyi) documents
the records.

## Render and parse

```python
import carve

html = carve.render("Hello *world*")["html"]
html_with_notes = carve.render("Hello", diagnostics=True)
tree = carve.parse("# Title", positions=True)["tree"]
parsed = carve.parse("# Title", diagnostics=True)
```

`carve.to_html(source, options=None)` remains as a string result convenience
function. `carve.call(request)` exposes the complete 0.2 JSON call set,
including `sourceBytes`, `decodeTree`, and `includeDependencies`.

## Options and safety

Pass a 0.2 option dictionary as the second argument. The engine rejects
unknown keys, values outside their declared range, and options a call cannot
use. `rawHtml` is false by default. Keep it false for untrusted documents.

```python
safe = carve.render(user_text, {"rawHtml": False, "urlPolicy": {"deny": ["javascript"]}})
static = carve.render(source, {"mode": "static", "profile": "comment"})
linked = carve.render("Hello :rocket:", {"symbols": {"rocket": "🚀"}})
```

The 0.1 `safe` keyword becomes `rawHtml` plus `urlPolicy`. The 0.1
`lowercase_heading_ids` setting becomes `headingIds`. Other renamed keys
include `sourceLines`, `smartTypography`, `strictLosses`, `alignTables`, and
the social URL templates in `social` (`mentionUrl`, `tagUrl`).

## Includes

The engine reads includes only when the caller gives a root. File identity is
part of the same option. The root must point to a readable directory.

```python
result = carve.render("{{ intro.crv }}", {
    "includes": {"root": "/absolute/docs", "file": "book.crv"}
})
```

## Diagnostics and trees

```python
warnings = carve.lint("# Title")["diagnostics"]
rendered = carve.render("# Title", diagnostics=True)
tree = carve.parse("# Title")["tree"]
written = carve.write(tree, "html")
```

Lint diagnostics carry `code`, `severity`, `channel`, `message`, and optional
`path`, `range`, `file`, and `foreignType`. `range.startOffset` and
`range.endOffset` count UTF-8 bytes, as in the 0.2 tooling contract. Convert
them before using them as Python string indices.

## Formatting and HTML import

`carve.fmt` and `carve.to_carve` run the canonical Carve writer.
`carve.import_document` and `carve.from_html` import HTML and return `tree`,
`source`, and `diagnostics`.

```python
carve.to_carve("# Hi")  # "= Hi\n"
carve.from_html("<p>Hello <strong>world</strong></p>")["source"]  # "Hello *world*\n"
```

## Standard extensions

The engine's standard extensions are provisional. `carve.extensions()` lists
them (`carve.cite`, `carve.imgFence.image`, `carve.imgFence.img`, `carve.tabs`,
`carve.wiki`). Select them with `extensions`, and their standard renderers
with `renderers`:

```python
carve.to_html(source, extensions=["carve.tabs"], renderers={"carve.tabs": "standard"})
carve.render(source, {"extensions": ["carve.wiki"]})
```

`renderers` also accepts Python callables through the native host. A callable
handles both channels; a dictionary with `interactive` and `static` keys selects
channels separately. Use `carve.render_with_host(source, tree=tree, renderers=...,
transforms=...)` for a supplied extension tree. A transform receives a copy of
the resolved JSON-shaped document and returns a document. The engine reports a
failed callback as `extension-renderer-failed` or `extension-transform-failed`.
This host path reads `mode`, `sections`, `rawHtml`, and `extensions` options.

## Pending engine features

`carve.to_markdown`, `carve.to_plain_text`, and `carve.to_ansi` route through
the writer registry. They raise `CarveError` with "writer not available yet"
until the pinned engine registers the `markdown`, `plain`, and `ansi` targets
(carve-rs issues 4327 and 4349). The 0.1 math block, list table, diagram,
glossary, and other bundled extensions are not ported to the Rust 0.2 host
yet (carve-rs issues 4341, 4342, and 4343). Markdown import is carve-rs issue
4344.

The 0.1 Markdown importer, stamps, decision trace, source patch tools, and
region-selection helper have no 0.2 core call. Use the 0.1 branch for those
workflows until a separate 0.2 host implementation is designed.
