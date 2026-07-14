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

# Dedicated explicit-list variant
html = carve.to_html_with_extensions(source, ["autolink"])

# Map `:name:` symbols to their values
carve.to_html("Ship it :rocket:", symbols={"rocket": "🚀"})
# -> '<p>Ship it 🚀</p>'

# Other renderers
carve.to_markdown(source)
carve.to_plain_text(source)
carve.to_ansi(source)

# Discover supported extension names
carve.extensions()
```

Passing an unknown extension name raises `ValueError`.

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

## Supported extensions

The string passed in `extensions=[...]` maps to a carve-rs extension:

| name                 | effect                                              |
|----------------------|-----------------------------------------------------|
| `autolink`           | turn bare URLs into links                            |
| `details`            | collapsible `<details>` blocks                       |
| `external_links`     | mark external links (rel/target)                     |
| `fenced_render`      | render fenced blocks of a target language (mermaid)  |
| `fenced_render_chart`| render fenced `chart` blocks (Chart.js)              |
| `heading_permalinks` | add permalink anchors to headings                    |
| `list_table`         | build tables from nested lists                        |
| `math_block`         | fenced math blocks                                   |
| `spoiler`            | spoiler / hidden-content inline                       |
| `tab_normalize`      | normalize tab indentation                            |
| `wikilinks`          | `[[wiki style]]` links                               |
| `citations`          | citation references                                  |
| `code-callouts`      | numbered callouts in fenced code blocks              |
