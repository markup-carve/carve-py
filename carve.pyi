"""Typed Carve 0.2 Python API over the Rust JSON boundary."""

from typing import Any, Dict, List, Optional, TypedDict

__version__: str

class EnginePanicError(Exception): ...
class CarveError(ValueError):
    name: str
    category: str
    status: int

class Range(TypedDict):
    startOffset: int
    endOffset: int

class Diagnostic(TypedDict, total=False):
    code: str
    severity: str
    channel: str
    message: str
    path: str
    range: Range
    file: str
    foreignType: str

class RenderResult(TypedDict, total=False):
    html: str
    diagnostics: List[Diagnostic]
    suppressedDiagnostics: int

class ParseResult(TypedDict, total=False):
    tree: Dict[str, Any]
    diagnostics: List[Diagnostic]
    suppressedDiagnostics: int

class LintResult(TypedDict):
    diagnostics: List[Diagnostic]

class FormatResult(TypedDict):
    source: str
    diagnostics: List[Diagnostic]

class WriteResult(TypedDict):
    output: str
    diagnostics: List[Diagnostic]

Options = Dict[str, Any]

def call(request: Dict[str, Any]) -> Dict[str, Any]:
    """Run one public Carve 0.2 JSON call and return its successful result."""
    ...

def render(source: str, options: Optional[Options] = None, *, diagnostics: bool = False) -> RenderResult: ...
def parse(source: str, options: Optional[Options] = None, *, diagnostics: bool = False, positions: bool = True) -> ParseResult: ...
def parse_json(source: str, *, positions: bool = True) -> str: ...
def lint(source: str, options: Optional[Options] = None) -> LintResult: ...
def fmt(source: str, options: Optional[Options] = None) -> FormatResult: ...
def import_document(source: str, source_format: str = "html", options: Optional[Options] = None) -> Dict[str, Any]: ...
def write(tree: Dict[str, Any], target: str = "html", options: Optional[Options] = None) -> WriteResult: ...

def to_html(source: str, options: Optional[Options] = None, *, extensions: Optional[List[str]] = None, renderers: Optional[Dict[str, Any]] = None) -> str: ...
def to_html_with_extensions(source: str, extensions: List[str], options: Optional[Options] = None) -> str: ...
def extensions() -> List[str]: ...
def to_carve(source: str, options: Optional[Options] = None) -> str: ...
def to_markdown(source: str) -> str: ...
def to_plain_text(source: str) -> str: ...
def to_ansi(source: str) -> str: ...
def from_html(source: str) -> Dict[str, Any]: ...
def from_markdown(source: str) -> Dict[str, Any]: ...
def _panic_probe() -> str: ...
