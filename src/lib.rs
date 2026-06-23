//! PyO3 native binding exposing the `carve` (carve-rs) engine to Python.
//!
//! The compiled module is imported as `import carve` and provides:
//!   - `carve.to_html(source)`                       core, no extensions
//!   - `carve.to_html(source, extensions=[...])`     named extensions
//!   - `carve.to_html_with_extensions(source, exts)` explicit variant
//!   - `carve.to_markdown(source)` / `to_plain_text(source)` / `to_ansi(source)`
//!   - `carve.extensions()`                          list of supported names
//!   - `carve.__version__`
//!
//! We never reimplement the parser; every call delegates to carve-rs.

use carve_rs::{
    Autolink, CarveExtension, Citations, Details, ExternalLinks, FencedRender, HeadingPermalinks,
    ListTable, MathBlock, Options, Spoiler, TabNormalize, Wikilinks,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// Map a Python-facing extension name to an owned boxed carve-rs extension.
///
/// Returns an error for unknown names so typos surface immediately in Python
/// rather than silently producing core output.
fn build_extension(name: &str) -> PyResult<Box<dyn CarveExtension>> {
    let ext: Box<dyn CarveExtension> = match name {
        "autolink" => Box::new(Autolink::new()),
        "details" => Box::new(Details::new()),
        "external_links" => Box::new(ExternalLinks::new()),
        // FencedRender needs a target language; "mermaid" is the canonical
        // diagram use case. Callers needing another language should extend
        // this binding; the string map keeps the common case ergonomic.
        "fenced_render" => Box::new(FencedRender::new("mermaid")),
        "heading_permalinks" => Box::new(HeadingPermalinks::new()),
        "list_table" => Box::new(ListTable::new()),
        "math_block" => Box::new(MathBlock::new()),
        "spoiler" => Box::new(Spoiler::new()),
        "tab_normalize" => Box::new(TabNormalize::new()),
        "wikilinks" => Box::new(Wikilinks::new()),
        "citations" => Box::new(Citations::new()),
        other => {
            return Err(PyValueError::new_err(format!(
                "unknown carve extension: {other:?} (supported: {})",
                SUPPORTED.join(", ")
            )));
        }
    };
    Ok(ext)
}

/// The canonical list of extension names accepted by the binding.
const SUPPORTED: &[&str] = &[
    "autolink",
    "details",
    "external_links",
    "fenced_render",
    "heading_permalinks",
    "list_table",
    "math_block",
    "spoiler",
    "tab_normalize",
    "wikilinks",
    "citations",
];

/// Build an owned vec of boxed extensions from the requested names.
fn boxed_extensions(names: &[String]) -> PyResult<Vec<Box<dyn CarveExtension>>> {
    names.iter().map(|n| build_extension(n)).collect()
}

/// Run `f` with an `Options` that borrows the given owned extensions.
///
/// `Options<'a>` holds `&'a dyn CarveExtension`, so the owned boxes must
/// outlive the borrow. Both live in this single stack frame, satisfying the
/// lifetime without leaking.
fn render<F>(source: &str, names: &[String], f: F) -> PyResult<String>
where
    F: FnOnce(&str, &Options<'_>) -> String,
{
    let owned = boxed_extensions(names)?;
    let mut options = Options::new();
    for ext in &owned {
        options = options.with_extension(ext.as_ref());
    }
    Ok(f(source, &options))
}

/// Convert Carve source to HTML.
///
/// With no `extensions`, this is the core renderer (identical to carve-rs
/// `to_html`). Pass a list of extension names to enable opt-in behavior.
#[pyfunction]
#[pyo3(signature = (source, extensions = None))]
fn to_html(source: &str, extensions: Option<Vec<String>>) -> PyResult<String> {
    match extensions {
        None => Ok(carve_rs::to_html(source)),
        Some(names) if names.is_empty() => Ok(carve_rs::to_html(source)),
        Some(names) => render(source, &names, carve_rs::to_html_with_options),
    }
}

/// Convert Carve source to HTML with an explicit (required) extension list.
#[pyfunction]
fn to_html_with_extensions(source: &str, extensions: Vec<String>) -> PyResult<String> {
    if extensions.is_empty() {
        return Ok(carve_rs::to_html(source));
    }
    render(source, &extensions, carve_rs::to_html_with_options)
}

/// True when no extensions were requested (None or empty list).
fn is_core(extensions: &Option<Vec<String>>) -> bool {
    extensions.as_ref().is_none_or(|v| v.is_empty())
}

/// Convert Carve source to Markdown.
#[pyfunction]
#[pyo3(signature = (source, extensions = None))]
fn to_markdown(source: &str, extensions: Option<Vec<String>>) -> PyResult<String> {
    if is_core(&extensions) {
        return Ok(carve_rs::to_markdown(source));
    }
    render(source, &extensions.unwrap(), carve_rs::to_markdown_with_options)
}

/// Convert Carve source to plain text.
#[pyfunction]
#[pyo3(signature = (source, extensions = None))]
fn to_plain_text(source: &str, extensions: Option<Vec<String>>) -> PyResult<String> {
    if is_core(&extensions) {
        return Ok(carve_rs::to_plain_text(source));
    }
    render(
        source,
        &extensions.unwrap(),
        carve_rs::to_plain_text_with_options,
    )
}

/// Convert Carve source to ANSI-colored terminal text.
#[pyfunction]
#[pyo3(signature = (source, extensions = None))]
fn to_ansi(source: &str, extensions: Option<Vec<String>>) -> PyResult<String> {
    if is_core(&extensions) {
        return Ok(carve_rs::to_ansi(source));
    }
    render(source, &extensions.unwrap(), carve_rs::to_ansi_with_options)
}

/// Return the list of supported extension names.
#[pyfunction]
fn extensions() -> Vec<String> {
    SUPPORTED.iter().map(|s| s.to_string()).collect()
}

#[pymodule]
fn carve(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(to_html, m)?)?;
    m.add_function(wrap_pyfunction!(to_html_with_extensions, m)?)?;
    m.add_function(wrap_pyfunction!(to_markdown, m)?)?;
    m.add_function(wrap_pyfunction!(to_plain_text, m)?)?;
    m.add_function(wrap_pyfunction!(to_ansi, m)?)?;
    m.add_function(wrap_pyfunction!(extensions, m)?)?;
    Ok(())
}
