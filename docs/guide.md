# Carve 0.2 Python guide

This branch uses the unreleased `carve2` engine at the git revision in
`Cargo.lock`. Its Python functions return dictionaries with the same camelCase
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

## Pending engine features

`carve.fmt`, `carve.to_carve`, `carve.import_document`, and `carve.from_html`
remain callable. They raise `CarveError` with an availability message until
the source writer or HTML importer is registered in the pinned engine.
`carve.to_markdown`, `carve.to_plain_text`, and `carve.to_ansi` likewise route
through the writer registry. Their targets are pending. The extension host is
provisional, so 0.1 extension registrations and Python callback renderers are
not active on this branch. The engine work is tracked in carve-rs issues
4327, 4328, and 4329.

The 0.1 Markdown importer, stamps, decision trace, source patch tools, and
region-selection helper have no 0.2 core call. Use the 0.1 branch for those
workflows until a separate 0.2 host implementation is designed.
