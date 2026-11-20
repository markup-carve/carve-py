//! Python transport for the public Carve 0.2 JSON call boundary.

mod host;
mod host_options;

use pyo3::exceptions::{PyException, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyList, PyString};
use std::cell::RefCell;
use std::panic::{self, AssertUnwindSafe};
use std::sync::Once;

pyo3::create_exception!(carve, EnginePanicError, PyException);
pyo3::create_exception!(carve, CarveError, PyValueError);

thread_local! {
    static PANIC_LOCATION: RefCell<Option<String>> = const { RefCell::new(None) };
}

fn install_panic_hook() {
    static ONCE: Once = Once::new();
    ONCE.call_once(|| {
        let previous = panic::take_hook();
        panic::set_hook(Box::new(move |info| {
            PANIC_LOCATION.with(|slot| {
                *slot.borrow_mut() = info
                    .location()
                    .map(|l| format!("{}:{}:{}", l.file(), l.line(), l.column()));
            });
            previous(info);
        }));
    });
}

fn guard<T>(f: impl FnOnce() -> PyResult<T>) -> PyResult<T> {
    match panic::catch_unwind(AssertUnwindSafe(f)) {
        Ok(result) => result,
        Err(payload) => {
            let message = payload
                .downcast_ref::<String>()
                .cloned()
                .or_else(|| payload.downcast_ref::<&str>().map(|s| (*s).to_string()))
                .unwrap_or_else(|| "panic".to_string());
            let location = PANIC_LOCATION.with(|slot| slot.borrow_mut().take());
            Err(EnginePanicError::new_err(match location {
                Some(at) => format!("the Carve engine panicked at {at}: {message}"),
                None => format!("the Carve engine panicked: {message}"),
            }))
        }
    }
}

fn option_error(py: Python<'_>, message: impl Into<String>) -> PyErr {
    let error = CarveError::new_err(message.into());
    error
        .value(py)
        .setattr("name", "CarveOptionError")
        .expect("CarveError metadata");
    error
        .value(py)
        .setattr("category", "usage")
        .expect("CarveError metadata");
    error
        .value(py)
        .setattr("status", 2)
        .expect("CarveError metadata");
    error
}

/// Replace lone surrogates as the 0.1 binding did before entering Rust.
struct Source(String);

impl<'py> FromPyObject<'_, 'py> for Source {
    type Error = PyErr;

    fn extract(obj: pyo3::Borrowed<'_, 'py, PyAny>) -> Result<Self, Self::Error> {
        let bytes: Vec<u8> = obj
            .cast::<PyString>()?
            .call_method1("encode", ("utf-16-le", "surrogatepass"))?
            .extract()?;
        let units = bytes
            .chunks_exact(2)
            .map(|pair| u16::from_le_bytes([pair[0], pair[1]]));
        Ok(Self(
            std::char::decode_utf16(units)
                .map(|character| character.unwrap_or('\u{FFFD}'))
                .collect(),
        ))
    }
}

fn request<'py>(
    py: Python<'py>,
    name: &str,
    source: Option<&str>,
    options: Option<Bound<'py, PyDict>>,
) -> PyResult<Bound<'py, PyDict>> {
    let req = PyDict::new(py);
    req.set_item("call", name)?;
    if let Some(source) = source {
        req.set_item("source", source)?;
    }
    if let Some(options) = options {
        req.set_item("options", options)?;
    }
    Ok(req)
}

fn execute(py: Python<'_>, req: &Bound<'_, PyDict>) -> PyResult<Py<PyAny>> {
    let json = py.import("json")?;
    let encoded: String = json.call_method1("dumps", (req,))?.extract()?;
    let response = ::carve::api::json::call(&encoded);
    let decoded = json.call_method1("loads", (response,))?;
    let decoded = decoded.cast::<PyDict>()?;
    if let Some(error) = decoded.get_item("error")? {
        let error = error.cast::<PyDict>()?;
        let message: String = error
            .get_item("message")?
            .ok_or_else(|| CarveError::new_err("engine error has no message"))?
            .extract()?;
        let message = if message.contains("not available") || message.contains("unsupported") {
            match req
                .get_item("target")?
                .and_then(|value| value.extract::<String>().ok())
            {
                Some(target) => format!("{target} writer not available yet: {message}"),
                None => format!("{message}; engine feature not available yet"),
            }
        } else {
            message
        };
        let exception = CarveError::new_err(message);
        for key in ["name", "category", "status"] {
            if let Some(value) = error.get_item(key)? {
                exception.value(py).setattr(key, value)?;
            }
        }
        return Err(exception);
    }
    Ok(decoded
        .get_item("ok")?
        .ok_or_else(|| CarveError::new_err("engine response has no result"))?
        .unbind())
}

#[pyfunction]
fn call(py: Python<'_>, request: Bound<'_, PyDict>) -> PyResult<Py<PyAny>> {
    guard(|| {
        let normalized = PyDict::new(py);
        for (key, value) in request.iter() {
            normalized.set_item(key, value)?;
        }
        if let Some(source) = normalized.get_item("source")? {
            if source.is_instance_of::<PyString>() {
                let text: Source = source.extract()?;
                normalized.set_item("source", text.0)?;
            }
        }
        execute(py, &normalized)
    })
}

#[pyfunction]
#[pyo3(signature = (source, options = None, *, diagnostics = false))]
fn render(
    py: Python<'_>,
    source: Source,
    options: Option<Bound<'_, PyDict>>,
    diagnostics: bool,
) -> PyResult<Py<PyAny>> {
    guard(|| {
        execute(
            py,
            &request(
                py,
                if diagnostics {
                    "renderWithDiagnostics"
                } else {
                    "render"
                },
                Some(&source.0),
                options,
            )?,
        )
    })
}

#[pyfunction]
#[pyo3(signature = (source, options = None, *, diagnostics = false, positions = true))]
fn parse(
    py: Python<'_>,
    source: Source,
    options: Option<Bound<'_, PyDict>>,
    diagnostics: bool,
    positions: bool,
) -> PyResult<Py<PyAny>> {
    guard(|| {
        let req = request(
            py,
            if diagnostics {
                "parseWithDiagnostics"
            } else {
                "parse"
            },
            Some(&source.0),
            options,
        )?;
        req.set_item("positions", positions)?;
        execute(py, &req)
    })
}

#[pyfunction]
#[pyo3(signature = (source, *, positions = true))]
fn parse_json(py: Python<'_>, source: Source, positions: bool) -> PyResult<String> {
    guard(|| {
        let parsed = request(py, "parse", Some(&source.0), None)?;
        parsed.set_item("positions", positions)?;
        let parsed = execute(py, &parsed)?;
        let tree = parsed
            .bind(py)
            .cast::<PyDict>()?
            .get_item("tree")?
            .ok_or_else(|| CarveError::new_err("parse result has no tree"))?;
        let req = request(py, "encodeTree", None, None)?;
        req.set_item("tree", tree)?;
        let encoded = execute(py, &req)?;
        encoded
            .bind(py)
            .cast::<PyDict>()?
            .get_item("json")?
            .ok_or_else(|| CarveError::new_err("encodeTree result has no json"))?
            .extract()
    })
}

#[pyfunction]
#[pyo3(signature = (source, options = None))]
fn lint(py: Python<'_>, source: Source, options: Option<Bound<'_, PyDict>>) -> PyResult<Py<PyAny>> {
    guard(|| execute(py, &request(py, "lint", Some(&source.0), options)?))
}

#[pyfunction]
#[pyo3(signature = (source, options = None))]
fn fmt(py: Python<'_>, source: Source, options: Option<Bound<'_, PyDict>>) -> PyResult<Py<PyAny>> {
    guard(|| {
        execute(
            py,
            &request(py, "formatWithDiagnostics", Some(&source.0), options)?,
        )
    })
}

#[pyfunction]
#[pyo3(signature = (source, source_format = "html", options = None))]
fn import_document(
    py: Python<'_>,
    source: Source,
    source_format: &str,
    options: Option<Bound<'_, PyDict>>,
) -> PyResult<Py<PyAny>> {
    guard(|| {
        if source_format != "html" {
            return Err(option_error(
                py,
                format!("{source_format} import is not a Carve 0.2 core format"),
            ));
        }
        let req = request(py, "importDocument", Some(&source.0), options)?;
        req.set_item("from", source_format)?;
        execute(py, &req)
    })
}

#[pyfunction]
#[pyo3(signature = (tree, target = "html", options = None))]
fn write(
    py: Python<'_>,
    tree: Bound<'_, PyAny>,
    target: &str,
    options: Option<Bound<'_, PyDict>>,
) -> PyResult<Py<PyAny>> {
    guard(|| {
        let req = request(py, "writeWithDiagnostics", None, options)?;
        req.set_item("tree", tree)?;
        req.set_item("target", target)?;
        execute(py, &req)
    })
}

/// The standard extensions the engine enables over the JSON boundary (C2-X-039).
const STANDARD_EXTENSIONS: &[&str] = &[
    "carve.cite",
    "carve.codeCallouts",
    "carve.codeGroup",
    "carve.colorSwatch",
    "carve.details",
    "carve.fencedRender.abc",
    "carve.fencedRender.chart",
    "carve.fencedRender.d2",
    "carve.fencedRender.graphviz",
    "carve.fencedRender.mermaid",
    "carve.fencedRender.plantuml",
    "carve.fencedRender.vega-lite",
    "carve.fencedRender.wavedrom",
    "carve.glossary",
    "carve.imgFence.image",
    "carve.imgFence.img",
    "carve.index",
    "carve.inlineFootnotesToParentheses",
    "carve.listTable",
    "carve.mathBlock",
    "carve.references",
    "carve.semanticSpan",
    "carve.smartQuotes",
    "carve.spoiler",
    "carve.spoilerBlock",
    "carve.tabNormalize",
    "carve.tabs",
    "carve.wiki",
];

#[pyfunction]
#[pyo3(signature = (source, options = None, *, tree = None, renderers = None, transforms = None))]
fn render_with_host(
    py: Python<'_>,
    source: Source,
    options: Option<Bound<'_, PyDict>>,
    tree: Option<Bound<'_, PyAny>>,
    renderers: Option<Bound<'_, PyDict>>,
    transforms: Option<Bound<'_, PyList>>,
) -> PyResult<Py<PyAny>> {
    guard(|| {
        host::render_host(
            py,
            &source.0,
            tree.as_ref(),
            options.as_ref(),
            renderers.as_ref(),
            transforms.as_ref(),
        )
    })
}

#[pyfunction]
#[pyo3(signature = (source, options = None, *, extensions = None, renderers = None, transforms = None))]
fn to_html(
    py: Python<'_>,
    source: Source,
    options: Option<Bound<'_, PyDict>>,
    extensions: Option<Vec<String>>,
    renderers: Option<Bound<'_, PyDict>>,
    transforms: Option<Bound<'_, PyList>>,
) -> PyResult<String> {
    guard(|| {
        let merged = PyDict::new(py);
        if let Some(options) = options {
            merged.update(options.as_mapping())?;
        }
        if let Some(names) = extensions.filter(|names| !names.is_empty()) {
            merged.set_item("extensions", names)?;
        }
        if let Some(items) = renderers.as_ref() {
            for (name, renderer) in items.iter() {
                let name: String = name.extract()?;
                if STANDARD_EXTENSIONS.contains(&name.as_str())
                    && (renderer.is_callable()
                        || renderer
                            .cast::<PyDict>()
                            .ok()
                            .is_some_and(|map| map.get_item("standard").ok().flatten().is_none()))
                {
                    return Err(option_error(py, format!("renderers: {name}: standard extension callbacks are not selected by the JSON options (C2-T-010)")));
                }
            }
        }
        if transforms.as_ref().is_some_and(|items| !items.is_empty())
            || renderers.as_ref().is_some_and(|items| {
                items.iter().any(|(_, renderer)| {
                    renderer.is_callable() || renderer.is_instance_of::<PyDict>()
                })
            })
        {
            let rendered = host::render_host(
                py,
                &source.0,
                None,
                Some(&merged),
                renderers.as_ref(),
                transforms.as_ref(),
            )?;
            return rendered
                .bind(py)
                .cast::<PyDict>()?
                .get_item("html")?
                .ok_or_else(|| CarveError::new_err("render result has no html"))?
                .extract();
        }
        if let Some(renderers) = renderers.filter(|items| !items.is_empty()) {
            for (name, renderer) in renderers.iter() {
                if !renderer.is_instance_of::<PyString>()
                    && !renderer
                        .cast::<PyDict>()
                        .ok()
                        .is_some_and(|map| map.get_item("standard").ok().flatten().is_some())
                {
                    return Err(option_error(
                        py,
                        format!(
                            "renderers: {name}: host callback renderers have no JSON form (C2-T-010); use \"standard\""
                        ),
                    ));
                }
            }
            merged.set_item("renderers", renderers)?;
        }
        let result = execute(py, &request(py, "render", Some(&source.0), Some(merged))?)?;
        result
            .bind(py)
            .cast::<PyDict>()?
            .get_item("html")?
            .ok_or_else(|| CarveError::new_err("render result has no html"))?
            .extract()
    })
}

#[pyfunction]
#[pyo3(signature = (source, extensions, options = None))]
fn to_html_with_extensions(
    py: Python<'_>,
    source: Source,
    extensions: Vec<String>,
    options: Option<Bound<'_, PyDict>>,
) -> PyResult<String> {
    guard(|| to_html(py, source, options, Some(extensions), None, None))
}

#[pyfunction]
fn extensions() -> PyResult<Vec<String>> {
    guard(|| {
        Ok(STANDARD_EXTENSIONS
            .iter()
            .map(|name| name.to_string())
            .collect())
    })
}

#[pyfunction]
#[pyo3(signature = (source, options = None))]
fn to_carve(
    py: Python<'_>,
    source: Source,
    options: Option<Bound<'_, PyDict>>,
) -> PyResult<String> {
    guard(|| {
        let result = execute(py, &request(py, "format", Some(&source.0), options)?)?;
        result
            .bind(py)
            .cast::<PyDict>()?
            .get_item("source")?
            .ok_or_else(|| CarveError::new_err("format result has no source"))?
            .extract()
    })
}

fn write_source(py: Python<'_>, source: Source, target: &str) -> PyResult<String> {
    let parsed = execute(py, &request(py, "parse", Some(&source.0), None)?)?;
    let tree = parsed
        .bind(py)
        .cast::<PyDict>()?
        .get_item("tree")?
        .ok_or_else(|| CarveError::new_err("parse result has no tree"))?;
    let req = request(py, "write", None, None)?;
    req.set_item("tree", tree)?;
    req.set_item("target", target)?;
    let result = execute(py, &req)?;
    result
        .bind(py)
        .cast::<PyDict>()?
        .get_item("output")?
        .ok_or_else(|| CarveError::new_err("write result has no output"))?
        .extract()
}

#[pyfunction]
fn to_markdown(py: Python<'_>, source: Source) -> PyResult<String> {
    guard(|| write_source(py, source, "markdown"))
}
#[pyfunction]
fn to_plain_text(py: Python<'_>, source: Source) -> PyResult<String> {
    guard(|| write_source(py, source, "plain"))
}
#[pyfunction]
fn to_ansi(py: Python<'_>, source: Source) -> PyResult<String> {
    guard(|| write_source(py, source, "ansi"))
}
#[pyfunction]
fn from_html(py: Python<'_>, source: Source) -> PyResult<Py<PyAny>> {
    guard(|| {
        let req = request(py, "importDocument", Some(&source.0), None)?;
        req.set_item("from", "html")?;
        execute(py, &req)
    })
}

#[pyfunction]
fn from_markdown(py: Python<'_>, _source: Source) -> PyResult<Py<PyAny>> {
    guard(|| {
        Err(option_error(
            py,
            "Markdown import is not part of the Carve 0.2 core importer (C2-T-003)",
        ))
    })
}

#[pyfunction]
fn _panic_probe() -> PyResult<String> {
    guard(|| panic!("deliberate panic from the Carve extension panic probe"))
}

#[pymodule]
fn carve(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    install_panic_hook();
    m.add("CarveError", m.py().get_type::<CarveError>())?;
    m.add("EnginePanicError", m.py().get_type::<EnginePanicError>())?;
    m.add_function(wrap_pyfunction!(call, m)?)?;
    m.add_function(wrap_pyfunction!(render, m)?)?;
    m.add_function(wrap_pyfunction!(parse, m)?)?;
    m.add_function(wrap_pyfunction!(parse_json, m)?)?;
    m.add_function(wrap_pyfunction!(lint, m)?)?;
    m.add_function(wrap_pyfunction!(fmt, m)?)?;
    m.add_function(wrap_pyfunction!(import_document, m)?)?;
    m.add_function(wrap_pyfunction!(write, m)?)?;
    m.add_function(wrap_pyfunction!(to_html, m)?)?;
    m.add_function(wrap_pyfunction!(render_with_host, m)?)?;
    m.add_function(wrap_pyfunction!(to_html_with_extensions, m)?)?;
    m.add_function(wrap_pyfunction!(extensions, m)?)?;
    m.add_function(wrap_pyfunction!(to_carve, m)?)?;
    m.add_function(wrap_pyfunction!(to_markdown, m)?)?;
    m.add_function(wrap_pyfunction!(to_plain_text, m)?)?;
    m.add_function(wrap_pyfunction!(to_ansi, m)?)?;
    m.add_function(wrap_pyfunction!(from_html, m)?)?;
    m.add_function(wrap_pyfunction!(from_markdown, m)?)?;
    m.add_function(wrap_pyfunction!(_panic_probe, m)?)?;
    Ok(())
}
