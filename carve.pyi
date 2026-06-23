"""Type stubs for the `carve` native binding (PyO3 over carve-rs)."""

from typing import List, Optional

__version__: str

def to_html(source: str, extensions: Optional[List[str]] = None) -> str:
    """Convert Carve source to HTML.

    With no ``extensions`` (or an empty list) this is the core renderer,
    identical to carve-rs ``to_html``. Pass extension names to enable opt-in
    behavior. Raises ``ValueError`` for an unknown extension name.
    """
    ...

def to_html_with_extensions(source: str, extensions: List[str]) -> str:
    """Convert Carve source to HTML with an explicit extension list."""
    ...

def to_markdown(source: str, extensions: Optional[List[str]] = None) -> str:
    """Convert Carve source to Markdown."""
    ...

def to_plain_text(source: str, extensions: Optional[List[str]] = None) -> str:
    """Convert Carve source to plain text."""
    ...

def to_ansi(source: str, extensions: Optional[List[str]] = None) -> str:
    """Convert Carve source to ANSI-colored terminal text."""
    ...

def extensions() -> List[str]:
    """Return the list of supported extension names."""
    ...
