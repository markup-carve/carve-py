# Changelog

Notable changes to the `carve-lang` distribution (import name `carve`).

The engine is carve-rs, embedded at the revision recorded in `Cargo.lock`, so an
engine bump can change rendering without a line of Python changing. Engine bumps
therefore get an entry of their own.

## [Unreleased]

### Added

- Expose the engine-level `lowercase_heading_ids`, `positions`, `sections`,
  `source_lines`, `mention_url`, `tag_url` and `profile_base_host` options as
  keyword-only arguments on the HTML and AST entry points. An omitted argument
  keeps what the function did before: the engine's default for `to_html`, and
  positions ON for `parse` and `parse_json`, which have always returned spans.
- Wheels for four more platforms: manylinux aarch64, musllinux x86_64,
  musllinux aarch64 and macOS x86_64. `pip install carve-lang` previously fell
  back to the sdist on Alpine, on ARM Linux and on an Intel Mac, which needs a
  Rust toolchain at install time and otherwise fails with a compiler error.
  Every wheel is built and gated on its own architecture.

## 0.1.1 - 2026-08-18

### Security

- A list-valued URL attribute is probed at every candidate, not at its head
  (PART 9 section 25, markup-carve/carve#1320). The sanitizer read only the
  leading scheme of the value, which vouches for the whole value only where the
  whole value is one URL, so `srcset="safe.png 1x, javascript:alert(1) 2x"`
  passed on its second entry. `srcset`, `imagesrcset`, `ping` and `attributionsrc` are
  now split and every candidate is read. The engine embedded in `0.1.0`
  predates the fix, so every wheel published so far carries the defect.

### Everything else

- Take the extension list from the engine's registry instead of a hand-written
  copy. Twelve extensions that carve-rs already had become reachable from
  Python: glossary, index, table of contents (and `::: toc` placement), heading
  numbers, heading references, heading level shift, code groups, the img fence,
  color swatches, smart quotes, and tabs. `extensions()` now reports 31 names
  rather than 19.
- Registry keys are kebab-case (`math-block`), and the snake_case spellings this
  binding has always taken (`math_block`) keep working, so existing
  configuration is unaffected.
- Embed carve-rs `0.1.3` (`a33c42ad`). Rendering changes an existing document can see:
  a table header cell now carries `scope` (`col` in the leading header-row run,
  `row` below it, PART 10 SST9); the nine compact semantic names on an inline
  span render as the element that spells them; a caption on a quote is a
  figure caption again rather than an attribution; an abbreviation expands
  inside a span and inside any inline container; an attribute needs a separator
  before the next one, and a value-less attribute writes as a boolean; a
  reference resolves inside an inline note, and a footnote inside an unresolved
  reference stays a footnote; `attrs.keyValues` in the exported AST serializes
  in the author's source order.
- Composite figures (PART 9 section 4c). A **bare** `::: figure` fence is one
  figure of ordered panels: it renders `<figure class="carve-figure-group">`
  wrapping a `<div class="carve-figure-panels">`, each panel a
  `<figure class="carve-figure-panel">`, and a `^ ` line after the closer
  becomes the group's `<figcaption>` instead of an ordinary paragraph. A fence
  carrying a title or a `[label]` is unaffected and stays a generic container.
- A table cell's attribute block binds after its kind and alignment markers, so
  `{...}` following a cell's `=` marker is read as attributes rather than
  rendered as cell text.

## 0.1.0 - 2026-08-12

First release.

- Embed carve-rs `4ddc24a0`, 40 commits ahead of the previous pin. Brings the
  exact AST span extents, fence trailing-blank fixes, and locale-aware smart
  quotes, and clears the last 5 corpus divergences. A `+`-continued table cell
  no longer reports a `pos`, which is what PART 12 requires of a reassembled
  node.
- Convert Carve source to HTML, Markdown, plain text, and ANSI
  (`to_html`, `to_markdown`, `to_plain_text`, `to_ansi`), byte-identical to
  carve-rs for the same input.
- Enable opt-in extensions by name (`extensions=[...]`, `to_html_with_extensions`,
  and `extensions()` for the supported list).
- Render statically with `mode="static"` and optional build-time `renderers` for
  diagram fences and math; a missing or failing renderer degrades to the
  construct's source rather than to nothing.
- Map `:name:` symbols with `symbols={...}`. Values are inserted as trusted raw
  output in the target format, so a symbols map must never be built from
  untrusted input.
- Restrict input with `profile=` (`full`, `article`, `comment`, `minimal`) and
  escape `=html` raw passthrough with `safe=True`. A profile rejection raises
  rather than returning the engine's empty string, which a caller could not
  distinguish from a document that legitimately rendered to nothing.
- Export the PART 12 AST (`parse`, `parse_json`), the interchange shape every
  Carve engine publishes.
- Read provenance markers written by `carve fmt --stamp` (`read_stamp`) and
  answer whether a document predates the targeted spec version (`needs_review`);
  an unstamped document answers "needs review".
- Ship abi3 wheels (`abi3-py38`), so one wheel per platform covers CPython 3.8+,
  with `carve.pyi` type stubs.
