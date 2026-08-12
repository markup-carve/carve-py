# Changelog

Notable changes to the `carve-lang` distribution (import name `carve`).

The engine is carve-rs, embedded at the revision recorded in `Cargo.lock`, so an
engine bump can change rendering without a line of Python changing. Engine bumps
therefore get an entry of their own.

## 0.1.1 - 2026-08-12

- Take the extension list from the engine's registry instead of a hand-written
  copy. Twelve extensions that carve-rs already had become reachable from
  Python: glossary, index, table of contents (and `::: toc` placement), heading
  numbers, heading references, heading level shift, code groups, the img fence,
  color swatches, smart quotes, and tabs. `extensions()` now reports 31 names
  rather than 19.
- Registry keys are kebab-case (`math-block`), and the snake_case spellings this
  binding has always taken (`math_block`) keep working, so existing
  configuration is unaffected.
- Embed carve-rs `17300594`.

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
