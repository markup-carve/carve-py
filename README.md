# carve (Python binding)

Native Python bindings for the [Carve](https://markup-carve.github.io/carve/)
markup language. This package is a thin [PyO3](https://pyo3.rs) binding over the
Rust implementation [carve-rs](https://github.com/markup-carve/carve-rs),
so the parser is not reimplemented in Python: every conversion delegates to the
same engine the Rust CLI and WASM builds use. Output is byte-identical to
carve-rs for the same input.

This unlocks the Python docs / data ecosystem (MkDocs, Sphinx, Pelican,
Jupyter/nbconvert) for Carve.

## Install

Wheels are abi3 (`abi3-py38`), so a single wheel covers CPython 3.8+.

From a built wheel:

```bash
pip install carve-lang
```

From source (needs a Rust toolchain, 1.75+):

```bash
pip install maturin
maturin develop --release      # build + install into the active venv
# or
maturin build --release        # produce a wheel under target/wheels/
```

## Usage

```python
import carve

print(carve.__version__)

# Core conversion (no extensions)
html = carve.to_html("# Hello *world*")
# -> '<section id="Hello-world">\n  <h1>Hello <strong>world</strong></h1>\n</section>'

# Inline emphasis: /italic/ and *bold*
carve.to_html("/italic/ and *bold*")

# Enable opt-in extensions by name
html = carve.to_html(source, extensions=["math_block", "list_table"])

# Configure enabled extensions (the mapping is keyword-only)
html = carve.to_html(
    source,
    extensions=["heading-permalinks", "tabs"],
    extension_options={
        "heading-permalinks": {"aria_label": "Back to text", "lowercase_ids": True},
        "tabs": {"mode": "aria"},
    },
)

# Dedicated explicit-list variant
html = carve.to_html_with_extensions(source, ["autolink"])

# Map `:name:` symbols to their values
carve.to_html("Ship it :rocket:", symbols={"rocket": "🚀"})
# -> '<p>Ship it 🚀</p>'

# Engine-level options are keyword-only. Omitting one preserves its engine default.
carve.to_html("# Mixed Case", lowercase_heading_ids=True)
carve.to_html("Hello @ada", mention_url="https://example.com/{}")

# Other renderers. They take the same engine options and `extension_options`.
carve.to_markdown(source)
carve.to_plain_text(source)
carve.to_ansi(source, lowercase_heading_ids=True)
carve.to_carve(source)

# Migration returns canonical Carve plus a machine-readable loss report.
carve.from_html('<p>Hello <strong>world</strong></p>')
carve.from_markdown('*em* and **strong**')

# Discover supported extension names
carve.extensions()
```

Passing an unknown extension name raises `ValueError`.
`extension_options` only accepts enabled extension names and their documented
option keys; unknown names, unknown keys, invalid enum values and options for an
extension that takes none are rejected instead of silently using defaults.

The names come from the engine itself, so `carve.extensions()` is the list this
build actually accepts rather than a list documented here that could fall behind
it. They are kebab-case (`math-block`, `table-of-contents`); the snake_case
spellings this binding has always taken (`math_block`) reach the same
extensions, so nothing written against the older names has to change.

## Linting

`carve.lint` reports constructs that parse and render, but not the way the
author meant. The defect class it catches is the silent one: the document
parses, the renderer emits something, and what the author wrote never reaches
the page.

```python
import carve

for warning in carve.lint("{#orphan .cls}\n\n"):
    print(warning["line"], warning["rule"], warning["message"])
```

```
1 unattached-block-attribute This block attribute reaches no block: ...
```

That one is the clearest case - `{#id .cls}` above a blank line attaches to
nothing, so the id and the class vanish and nothing anywhere says so.

Each warning is a dict:

| Key | What |
| --- | --- |
| `line`, `column` | 1-based, for reporting |
| `rule` | a stable id, shared with carve-js and carve-php - the same trigger reports the same id in every engine |
| `message` | what degrades, in prose |
| `start`, `end` | codepoint offsets into the source, 0-based, end exclusive |

`start` and `end` slice the offending text directly:

```python
source = "{#orphan .cls}\n\n"
warning = carve.lint(source)[0]
assert source[warning["start"]:warning["end"]] == "{#orphan .cls}"
```

**They are CODEPOINT offsets, not the byte offsets the Rust API reports.** That
conversion is deliberate and tested: a Rust caller slices `&str` with bytes, but
Python slices by codepoint, so passing them through unconverted mis-slices every
document carrying one non-ASCII character before a warning. The unit follows the
host language - carve-js converts the same positions to UTF-16 for the same
reason.

`extensions` is the only option accepted, because it is the only one the
engine's linter reads:

```python
carve.lint(source, extensions=["details"])
```

## The parsed AST

`carve.parse()` returns the document as Python data - the [PART 12 exchange
shape](https://markup-carve.github.io/carve/ast-json), the same tree every Carve
engine publishes, so a consumer written against one implementation reads
another's output.

```python
ast = carve.parse("# Title\n\nBody[^a].\n\n[^a]: note\n")

ast["type"]                        # "document"
[c["type"] for c in ast["children"]]   # ["heading", "paragraph", "footnote"]
ast["children"][0]["pos"]          # {"startLine": 1, "startColumn": 1, ...}

carve.parse_json(source)  # the same tree, as JSON bytes
```

The root carries exactly `type`, `children` and `srcByteLength`; frontmatter and
footnote definitions are block nodes inside `children`, not root fields. Every
node except the root carries `pos` when the engine could place it - 1-based
lines and columns, 0-based offsets, ends exclusive, counted in Unicode
**codepoints**, not bytes. A node the engine could not place, such as
reassembled table-cell text, carries no `pos` at all rather than an invented
one.

The serialization is the engine's own, so this binding publishes byte-identical
output to the `carve --json` CLI and to every other binding over carve-rs.

Every rendering entry point (`to_html`, `to_html_with_extensions`, `to_markdown`,
`to_plain_text`, `to_ansi`, `parse` and `parse_json`) also accepts keyword-only
`lowercase_heading_ids`, `positions`, `sections`, `source_lines`, `mention_url`,
`tag_url`, and `profile_base_host`. Boolean options accept `True` or `False`;
URL/host options accept strings. When omitted, each option retains the engine's
own default.

The keyword set is the same on every target so a host does not have to remember
which target takes which. Most of these options describe HTML markup, so on
`to_markdown` / `to_plain_text` / `to_ansi` they have nothing to change;
`lowercase_heading_ids` does change those three, because all four renderers
resolve `</#id>` crossrefs through the same heading index.

## Symbols

A `:name:` symbol renders its literal `:name:` source unless the name is in the
**symbols map** passed as the `symbols=` keyword (supported by `to_html` and
`to_html_with_extensions`):

```python
carve.to_html("Ship it :rocket: :shrug:", symbols={"rocket": "🚀"})
# -> '<p>Ship it 🚀 :shrug:</p>'   (an unmapped name stays literal)
```

The leading word-boundary guard is unaffected by an active map: `a:b:c`,
`10:30:` and `me@example.com` never become symbols.

> **Security: symbol values are TRUSTED RAW output.**
> A mapped value is inserted into the output **unescaped** - the same trust
> class as a `renderers` callable. `symbols={"b": "<b>x</b>"}` emits a real
> `<b>` element, not escaped text. This is deliberate (processor configuration
> is trusted). **Never build a symbols map out of untrusted / user-supplied
> input.**

## Untrusted input

Carve's normative hardening is always on and needs no argument: dangerous URL
schemes are blanked, event-handler attributes like `onclick` are dropped, and the
bidi override/isolate characters behind Trojan Source are removed from rendered
text.

Raw passthrough is the deliberate exception. A ` ```=html ` block or a
`` `…`{=html} `` span renders **verbatim** by design, so it is the one thing
input you did not author has to switch off:

``` python
html = carve.to_html(user_input, safe=True, profile="comment")
```

`safe=True` escapes those raw blocks and spans instead of emitting them. It is
HTML-only, because HTML is the only target that can emit live markup:
`to_markdown` escapes raw HTML, `to_plain_text` drops it, `to_ansi` keeps it as
terminal text.

`profile` restricts which constructs are allowed at all and caps input length -
`"full"`, `"article"`, `"comment"`, `"minimal"`, or `None`. It applies to every
target, including `to_markdown` / `to_plain_text` / `to_ansi`.

An unknown profile name raises `ValueError`, and so does a **rejection** - input
past the profile's max length, or a denied construct when the action is error:

``` python
carve.to_html("x" * 20_000, profile="minimal")
# ValueError: Profile violations: 'document' is not allowed: max_length_exceeded (...)
```

It raises rather than returning something that looks like output: the engine's
infallible entry point answers a rejection with an empty string, which a caller
cannot tell from a document that legitimately rendered to nothing.

Full recipe, defaults and threat model:
[Security](https://markup-carve.github.io/carve/security).

## Stored documents and spec versions

`carve fmt --stamp` (in any Carve engine) records the spec version a document was
last processed under. This binding reads that marker back, so a repository of
stored `.crv` files can be checked for documents predating a breaking spec
change:

``` python
carve.read_stamp(source)
# {'version': '0.1', 'generated_by': 'carve-php 0.1.0'}

carve.needs_review(source)   # True when the document predates this engine
```

An **unstamped** document answers `True`: its provenance is unknown, and assuming
it is current is the unsafe direction. Both marker forms are read, and a marker
written by any engine reads the same - the format is the contract, not any one
API.

What a version difference means is the
[versioning contract](https://markup-carve.github.io/carve/versioning): only
`[behavior]` changelog entries between the stamped version and yours can require
a document change.

## Supported extensions

The string passed in `extensions=[...]` maps to a carve-rs extension:

| name                 | effect                                              |
|----------------------|-----------------------------------------------------|
| `autolink`           | turn bare URLs into links                            |
| `details`            | collapsible `<details>` blocks                       |
| `external_links`     | mark external links (rel/target)                     |
| `fenced_render`      | render fenced blocks of a target language (mermaid)  |
| `fenced_render_chart`| render fenced `chart` blocks (Chart.js)              |
| `fenced_render_plantuml` | render `plantuml`/`puml` blocks (Kroki client)   |
| `fenced_render_graphviz` | render `dot`/`graphviz` blocks                   |
| `fenced_render_d2`   | render `d2` blocks                                   |
| `fenced_render_wavedrom` | render `wavedrom` blocks                         |
| `fenced_render_vega_lite`| render `vega-lite` blocks (Vega-Lite)            |
| `fenced_render_abc`  | render `abc` music-notation blocks                   |
| `heading_permalinks` | add permalink anchors to headings                    |
| `list_table`         | build tables from nested lists                        |
| `math_block`         | fenced math blocks                                   |
| `spoiler`            | spoiler / hidden-content inline                       |
| `tab_normalize`      | normalize tab indentation                            |
| `wikilinks`          | `[[wiki style]]` links                               |
| `citations`          | citation references                                  |
| `code-callouts`      | numbered callouts in fenced code blocks              |
