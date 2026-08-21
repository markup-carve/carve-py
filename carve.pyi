"""Type stubs for the `carve` native binding (PyO3 over carve-rs)."""

from typing import Any, Callable, Dict, List, Optional, Union

__version__: str

# A static-render callable. Diagram renderers (mermaid, chart, plantuml,
# graphviz, d2, wavedrom, vega-lite, abc), keyed by fence css class, take the
# construct source and return HTML: ``(str) -> str``. The math renderer takes
# the TeX source and a ``display`` flag (``True`` for block/display math,
# ``False`` for inline) and returns HTML: ``(str, bool) -> str``.
Renderer = Union[Callable[[str], str], Callable[[str, bool], str]]
ExtensionOptions = Dict[str, Dict[str, Any]]

def to_html(
    source: str,
    extensions: Optional[List[str]] = None,
    mode: str = "interactive",
    renderers: Optional[Dict[str, Renderer]] = None,
    symbols: Optional[Dict[str, str]] = None,
    safe: bool = False,
    profile: Optional[str] = None,
    *,
    extension_options: Optional[ExtensionOptions] = None,
    lowercase_heading_ids: Optional[bool] = None,
    positions: Optional[bool] = None,
    sections: Optional[bool] = None,
    source_lines: Optional[bool] = None,
    mention_url: Optional[str] = None,
    tag_url: Optional[str] = None,
    profile_base_host: Optional[str] = None,
) -> str:
    """Convert Carve source to HTML.

    With no ``extensions`` (or an empty list) this is the core renderer,
    identical to carve-rs ``to_html``. Pass extension names to enable opt-in
    behavior. Raises ``ValueError`` for an unknown extension name.

    ``mode`` is ``"interactive"`` (default) or ``"static"``; any other value
    raises ``ValueError``. Static mode flattens interactive constructs to
    self-contained HTML (no client scripts).

    ``renderers`` is an optional dict of build-time renderer callables consulted
    only on the static HTML path. Keys are a diagram fence css class
    (``"mermaid"``, ``"chart"``, ``"plantuml"``, ``"graphviz"``, ``"d2"``,
    ``"wavedrom"``, ``"vega-lite"``, ``"abc"``; callables ``(str) -> str``) or
    ``"math"`` (callable ``(str, bool) -> str``). An unknown key raises
    ``ValueError``. A missing renderer degrades that
    construct to its source (never blank). A renderer that raises or returns a
    non-string also degrades to source.

    ``symbols`` is an optional ``{name: value}`` map for ``:name:`` symbols. A
    mapped name renders its value; an unmapped ``:name:`` stays literal, and the
    leading word-boundary guard still holds (``a:b:c``, ``10:30:``,
    ``me@example.com`` never become symbols). Non-string keys/values raise
    ``TypeError``.

    .. warning::
       A mapped symbol value is inserted as **TRUSTED RAW output in the target
       format** - it is NOT escaped, the same trust class as ``renderers``. So
       ``symbols={"b": "<b>x</b>"}`` emits a real ``<b>`` element. This is
       deliberate: processor configuration is trusted. **Never build a symbols
       map out of untrusted / user-supplied input.**

    ``safe`` escapes ``=html`` raw blocks and spans instead of emitting them.
    Carve's normative hardening is always on and needs no argument (URL scheme
    denylist, event-handler attributes, the Trojan-Source bidi characters); raw
    passthrough is the deliberate exception, so it is the one thing untrusted
    input has to switch off. It applies to HTML only, the one target that can
    emit live markup.

    ``profile`` restricts which constructs are allowed at all and caps input
    length: ``"full"``, ``"article"``, ``"comment"``, ``"minimal"``, or ``None``
    for no profile. An unknown name raises ``ValueError``, and so does a
    profile REJECTION - input past the profile's max length, or a denied
    construct when the action is error. It is an exception rather than a return
    value because the engine's infallible entry point answers a rejection with
    an empty string, which a caller cannot tell from a document that
    legitimately rendered to nothing.
    """
    ...

def to_html_with_extensions(
    source: str,
    extensions: List[str],
    mode: str = "interactive",
    renderers: Optional[Dict[str, Renderer]] = None,
    symbols: Optional[Dict[str, str]] = None,
    safe: bool = False,
    profile: Optional[str] = None,
    *,
    extension_options: Optional[ExtensionOptions] = None,
    lowercase_heading_ids: Optional[bool] = None,
    positions: Optional[bool] = None,
    sections: Optional[bool] = None,
    source_lines: Optional[bool] = None,
    mention_url: Optional[str] = None,
    tag_url: Optional[str] = None,
    profile_base_host: Optional[str] = None,
) -> str:
    """Convert Carve source to HTML with an explicit extension list.

    Supports the same ``mode`` / ``renderers`` / ``symbols`` / ``safe`` /
    ``profile`` keywords as :func:`to_html` (including the trusted-raw contract
    on symbol values).
    """
    ...

def to_markdown(
    source: str,
    extensions: Optional[List[str]] = None,
    profile: Optional[str] = None,
    *,
    extension_options: Optional[ExtensionOptions] = None,
    lowercase_heading_ids: Optional[bool] = None,
    positions: Optional[bool] = None,
    sections: Optional[bool] = None,
    source_lines: Optional[bool] = None,
    mention_url: Optional[str] = None,
    tag_url: Optional[str] = None,
    profile_base_host: Optional[str] = None,
) -> str:
    """Convert Carve source to Markdown (inherently static; no ``mode``).

    ``profile`` behaves as in :func:`to_html`. There is no ``safe`` keyword:
    this target escapes raw HTML unconditionally, so it can never emit live
    markup and has nothing to switch off.

    The engine keywords of :func:`to_html` are accepted here too. Most of them
    describe HTML markup and have no effect on this target;
    ``lowercase_heading_ids`` does, because the renderer resolves ``</#id>``
    crossrefs through the same heading index the HTML renderer uses.
    """
    ...

def to_plain_text(
    source: str,
    extensions: Optional[List[str]] = None,
    profile: Optional[str] = None,
    *,
    extension_options: Optional[ExtensionOptions] = None,
    lowercase_heading_ids: Optional[bool] = None,
    positions: Optional[bool] = None,
    sections: Optional[bool] = None,
    source_lines: Optional[bool] = None,
    mention_url: Optional[str] = None,
    tag_url: Optional[str] = None,
    profile_base_host: Optional[str] = None,
) -> str:
    """Convert Carve source to plain text (inherently static; no ``mode``).

    ``profile`` behaves as in :func:`to_html`; there is no ``safe`` keyword (see
    :func:`to_markdown`).

    The engine keywords of :func:`to_html` are accepted here too. Most of them
    describe HTML markup and have no effect on this target;
    ``lowercase_heading_ids`` does, because the renderer resolves ``</#id>``
    crossrefs through the same heading index the HTML renderer uses.
    """
    ...

def to_ansi(
    source: str,
    extensions: Optional[List[str]] = None,
    profile: Optional[str] = None,
    *,
    extension_options: Optional[ExtensionOptions] = None,
    lowercase_heading_ids: Optional[bool] = None,
    positions: Optional[bool] = None,
    sections: Optional[bool] = None,
    source_lines: Optional[bool] = None,
    mention_url: Optional[str] = None,
    tag_url: Optional[str] = None,
    profile_base_host: Optional[str] = None,
) -> str:
    """Convert Carve source to ANSI-colored text (inherently static; no ``mode``).

    ``profile`` behaves as in :func:`to_html`; there is no ``safe`` keyword (see
    :func:`to_markdown`).

    The engine keywords of :func:`to_html` are accepted here too. Most of them
    describe HTML markup and have no effect on this target;
    ``lowercase_heading_ids`` does, because the renderer resolves ``</#id>``
    crossrefs through the same heading index the HTML renderer uses.
    """
    ...

def read_stamp(source: str) -> Optional[Dict[str, Optional[str]]]:
    """Read a document's provenance marker, as written by ``carve fmt --stamp``.

    Returns ``{"version": ..., "generated_by": ...}``, or ``None`` when the
    document carries no marker - the normal case for a hand-written document,
    meaning "unknown" rather than "current". ``generated_by`` is ``None`` when
    the marker records no writer.

    Both documented forms are read (the trailing ``%%`` line and the ``%%%``
    block), and a marker written by any Carve engine reads the same.
    """
    ...

def needs_review(source: str, current_version: Optional[str] = None) -> bool:
    """Whether a document predates the spec version this engine targets.

    An **unstamped** document answers ``True``: its provenance is unknown, and
    assuming it is current is the unsafe direction. Pass ``current_version`` to
    compare against something other than this engine's spec version.

    See https://markup-carve.github.io/carve/versioning for what a version
    difference means for a stored document.
    """
    ...

def parse(
    source: str,
    *,
    lowercase_heading_ids: Optional[bool] = None,
    positions: Optional[bool] = None,
    sections: Optional[bool] = None,
    source_lines: Optional[bool] = None,
    mention_url: Optional[str] = None,
    tag_url: Optional[str] = None,
    profile_base_host: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse Carve source and return its AST as Python data.

    The PART 12 exchange shape - the same tree every Carve engine publishes, so
    a consumer written against one implementation reads another's output. The
    root carries exactly ``type``, ``children`` and ``srcByteLength``;
    frontmatter and footnote definitions are block nodes inside ``children``.

    Every node except the root carries ``pos`` when the engine could place it; pass
    ``positions=False`` to leave the spans out:
    1-based lines and columns, 0-based offsets, ends exclusive, counted in
    Unicode **codepoints**. A node the engine could not place - reassembled
    text, a synthesized node - has no ``pos`` at all rather than an invented
    one.

    See https://markup-carve.github.io/carve/ast-json and its JSON Schema.
    """
    ...

def parse_json(
    source: str,
    *,
    lowercase_heading_ids: Optional[bool] = None,
    positions: Optional[bool] = None,
    sections: Optional[bool] = None,
    source_lines: Optional[bool] = None,
    mention_url: Optional[str] = None,
    tag_url: Optional[str] = None,
    profile_base_host: Optional[str] = None,
) -> str:
    """The same tree as :func:`parse`, as a JSON string.

    For a caller that stores or forwards the bytes rather than walking the tree,
    and so does not need the round trip through Python objects.
    """
    ...

def extensions() -> List[str]:
    """Return the list of supported extension names."""
    ...
