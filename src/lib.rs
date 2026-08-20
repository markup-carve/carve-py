//! PyO3 native binding exposing the `carve` (carve-rs) engine to Python.
//!
//! The compiled module is imported as `import carve` and provides:
//!   - `carve.to_html(source)`                       core, no extensions
//!   - `carve.to_html(source, extensions=[...])`     named extensions
//!   - `carve.to_html(source, mode='static')`        static render mode
//!   - `carve.to_html(source, renderers={...})`      build-time renderers
//!   - `carve.to_html(source, symbols={...})`        `:name:` symbol map
//!   - `carve.to_html_with_extensions(source, exts)` explicit variant
//!   - `carve.to_markdown(source)` / `to_plain_text(source)` / `to_ansi(source)`
//!   - `carve.extensions()`                          list of supported names
//!   - `carve.__version__`
//!
//! We never reimplement the parser; every call delegates to carve-rs.

use carve_rs::extensions::registry;
use carve_rs::{CarveExtension, Mode, Options, Profile, ProfileViolationError, StaticRenderers};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// HTML-escape a string for the renderer-failure fallback path.
///
/// carve-rs inserts a *present* static renderer's return value verbatim (it is
/// the renderer's job to produce safe HTML). So when our Python wrapper has to
/// fall back to the construct source - because the callable raised or returned
/// a non-string - that source MUST be escaped here, or a source containing HTML
/// (e.g. `<img onerror=...>`) would be emitted raw. The no-renderer path inside
/// carve-rs already escapes its `<pre><code>` source block; this keeps the
/// failing-renderer floor equally safe rather than a raw-passthrough hole.
fn escape_html(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars() {
        match ch {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(ch),
        }
    }
    out
}

/// The engine's registry key for a Python-facing name.
///
/// Registry keys are kebab-case; this binding has always accepted (and mkdocs
/// configs have always written) the snake_case spellings `external_links`,
/// `math_block`, `heading_permalinks` and friends. Both reach the same
/// extension, so neither spelling has to be memorized and no existing config
/// breaks.
fn registry_key(name: &str) -> String {
    name.replace('_', "-")
}

/// Map a Python-facing extension name to an owned boxed carve-rs extension.
///
/// Returns an error for unknown names so typos surface immediately in Python
/// rather than silently producing core output.
fn build_extension(name: &str) -> PyResult<Box<dyn CarveExtension>> {
    registry::by_key(&registry_key(name)).ok_or_else(|| {
        PyValueError::new_err(format!(
            "unknown carve extension: {name:?} (supported: {})",
            supported().join(", ")
        ))
    })
}

/// Every extension name this build accepts, taken from the engine.
///
/// This used to be a hand-written array beside a hand-written match, and
/// nothing compared either against carve-rs. An extension could land in the
/// engine and stay invisible from Python indefinitely, which is exactly what
/// happened: ten of them had accumulated - glossary, index, table of contents,
/// heading numbers and more - with no test able to notice.
fn supported() -> Vec<String> {
    registry::keys().map(str::to_string).collect()
}

/// Build an owned vec of boxed extensions from the requested names.
fn boxed_extensions(names: &[String]) -> PyResult<Vec<Box<dyn CarveExtension>>> {
    names.iter().map(|n| build_extension(n)).collect()
}

/// Map a Python-facing mode string to a carve-rs [`Mode`].
///
/// Rejects any unknown string with `ValueError`, mirroring the spec's
/// "MUST reject an unknown mode value" (no guessing). Omitting the mode in
/// Python defaults to `"interactive"`, so existing callers are unaffected.
fn parse_mode(mode: &str) -> PyResult<Mode> {
    match mode {
        "interactive" => Ok(Mode::Interactive),
        "static" => Ok(Mode::Static),
        other => Err(PyValueError::new_err(format!(
            "unknown carve render mode: {other:?} (supported: \"interactive\", \"static\")"
        ))),
    }
}

/// Wrap a Python diagram callable `(str) -> str` into a carve-rs closure.
///
/// The closure acquires the GIL, calls the Python callable with the construct
/// source, and returns its string result. If the callable raises or returns a
/// non-string, the closure degrades to the HTML-ESCAPED source, so a bad
/// renderer never produces blank output and can never inject raw HTML. (A
/// present renderer's return value is emitted verbatim by carve-rs, so the
/// fallback must escape rather than pass source through raw.) The callable is
/// stored as a thread-safe `Py<PyAny>`.
fn wrap_diagram(callable: Py<PyAny>) -> Box<dyn Fn(&str) -> String + 'static> {
    Box::new(move |src: &str| {
        Python::attach(|py| {
            match callable.call1(py, (src,)) {
                Ok(result) => match result.extract::<String>(py) {
                    Ok(s) => s,
                    // Non-string return: fall back to escaped source.
                    Err(_) => escape_html(src),
                },
                // Callable raised: fall back to escaped source rather than
                // propagating (the static path has no error channel).
                Err(_) => escape_html(src),
            }
        })
    })
}

/// Wrap a Python math callable `(str, bool) -> str` into a carve-rs closure.
///
/// Same contract as [`wrap_diagram`] (including the HTML-escaped fallback on a
/// raising / non-string-returning callable), but the callable receives the TeX
/// source and a `display` flag (`True` for block / display math, `False` for
/// inline).
type MathRenderer = Box<dyn Fn(&str, bool) -> String + 'static>;

fn wrap_math(callable: Py<PyAny>) -> MathRenderer {
    Box::new(move |tex: &str, display: bool| {
        Python::attach(|py| {
            match callable.call1(py, (tex, display)) {
                Ok(result) => match result.extract::<String>(py) {
                    Ok(s) => s,
                    // Non-string return: fall back to escaped source.
                    Err(_) => escape_html(tex),
                },
                // Callable raised: fall back to escaped source.
                Err(_) => escape_html(tex),
            }
        })
    })
}

/// Build a [`StaticRenderers`] from a Python dict of callables.
///
/// The `"math"` key takes a callable `(str, bool) -> str`. Every other key is a
/// **diagram fence css class** (`"mermaid"`, `"chart"`, `"plantuml"`,
/// `"graphviz"`, `"d2"`, ...) mapped to a callable `(str) -> str`; the engine
/// keys diagram renderers by css class, so a static render of that fence
/// consults the matching entry (else degrades to source).
fn build_renderers(renderers: &Bound<'_, PyDict>) -> PyResult<StaticRenderers> {
    let mut out = StaticRenderers::default();
    for (key, value) in renderers.iter() {
        let name: String = key.extract()?;
        let callable: Py<PyAny> = value.unbind();
        if name == "math" {
            out.math = Some(wrap_math(callable));
        } else if DIAGRAM_RENDERER_KEYS.contains(&name.as_str()) {
            // Keyed by the fence css class the preset emits.
            out.diagrams.insert(name, wrap_diagram(callable));
        } else {
            return Err(PyValueError::new_err(format!(
                "unknown renderer key: {name:?} (supported: \"math\", {})",
                DIAGRAM_RENDERER_KEYS
                    .iter()
                    .map(|k| format!("{k:?}"))
                    .collect::<Vec<_>>()
                    .join(", ")
            )));
        }
    }
    Ok(out)
}

/// Diagram-renderer keys accepted by `renderers={...}`: the fence css class each
/// FencedRender preset emits. Validated so a typo fails fast instead of
/// silently doing nothing.
const DIAGRAM_RENDERER_KEYS: &[&str] = &[
    "mermaid",
    "chart",
    "plantuml",
    "graphviz",
    "d2",
    "wavedrom",
    "abc",
    "vega-lite",
];

/// Lower a Python `symbols` dict into owned `(name, value)` pairs.
///
/// Keys and values must both be `str`; anything else raises `TypeError` from
/// the extraction, so a mistyped map fails fast instead of silently dropping
/// entries.
fn build_symbols(symbols: &Bound<'_, PyDict>) -> PyResult<Vec<(String, String)>> {
    let mut out = Vec::with_capacity(symbols.len());
    for (key, value) in symbols.iter() {
        let name: String = key.extract()?;
        let value: String = value.extract()?;
        out.push((name, value));
    }
    Ok(out)
}

/// Run `f` with an `Options` that borrows the given owned extensions, applying
/// the requested render mode, static renderers and symbol map.
///
/// `Options<'a>` holds `&'a dyn CarveExtension`, so the owned boxes must
/// outlive the borrow. Both live in this single stack frame, satisfying the
/// lifetime without leaking.
#[allow(clippy::too_many_arguments)]
fn render<F>(
    source: &str,
    names: &[String],
    mode: Mode,
    renderers: StaticRenderers,
    symbols: &[(String, String)],
    safe: bool,
    profile: Option<&str>,
    engine_options: EngineOptions,
    f: F,
) -> PyResult<String>
where
    F: FnOnce(&str, &Options<'_>) -> Result<String, ProfileViolationError>,
{
    let owned = boxed_extensions(names)?;
    let mut options = Options::new().with_mode(mode).with_renderers(renderers);
    for ext in &owned {
        options = options.with_extension(ext.as_ref());
    }
    for (name, value) in symbols {
        options = options.with_symbol(name.clone(), value.clone());
    }
    if safe {
        options = options.with_raw_html(false);
    }
    if let Some(name) = profile {
        options = options.with_profile(parse_profile(name)?);
    }
    options = engine_options.apply(options);
    // The fallible engine entry points, so a profile rejection raises instead of
    // returning an empty string. The infallible `to_*_with_options` wrappers are
    // `try_...().unwrap_or_default()`, which would make a rejected 20 KB comment
    // indistinguishable from a document that legitimately rendered to nothing.
    f(source, &options).map_err(|e| PyValueError::new_err(e.to_string()))
}

#[derive(Default, PartialEq)]
struct EngineOptions {
    lowercase_heading_ids: Option<bool>,
    positions: Option<bool>,
    sections: Option<bool>,
    source_lines: Option<bool>,
    mention_url: Option<String>,
    tag_url: Option<String>,
    profile_base_host: Option<String>,
}

impl EngineOptions {
    fn apply(self, mut options: Options<'_>) -> Options<'_> {
        if let Some(value) = self.lowercase_heading_ids {
            options = options.with_lowercase_heading_ids(value);
        }
        if let Some(value) = self.positions {
            options = options.with_positions(value);
        }
        if let Some(value) = self.sections {
            options = options.with_sections(value);
        }
        if let Some(value) = self.source_lines {
            options = options.with_source_lines(value);
        }
        if let Some(value) = self.mention_url {
            options = options.with_mention_url(value);
        }
        if let Some(value) = self.tag_url {
            options = options.with_tag_url(value);
        }
        if let Some(value) = self.profile_base_host {
            options = options.with_profile_base_host(value);
        }
        options
    }
}

/// Map a profile name to a [`Profile`], or raise Python ValueError.
///
/// The four presets are the engine's. An unknown name is reported rather than
/// silently ignored, matching [`parse_mode`].
fn parse_profile(name: &str) -> PyResult<Profile> {
    match name {
        "full" => Ok(Profile::full()),
        "article" => Ok(Profile::article()),
        "comment" => Ok(Profile::comment()),
        "minimal" => Ok(Profile::minimal()),
        other => Err(PyValueError::new_err(format!(
            "unknown carve profile: {other:?} (supported: \"full\", \"article\", \"comment\", \"minimal\")"
        ))),
    }
}

/// Resolve the mode string and renderers dict into the carve-rs types.
///
/// `mode` defaults to `"interactive"`. `renderers` is optional; absent it is an
/// empty `StaticRenderers`. Both are validated here so callers fail fast.
fn resolve_mode_and_renderers(
    mode: &str,
    renderers: Option<&Bound<'_, PyDict>>,
) -> PyResult<(Mode, StaticRenderers)> {
    let parsed_mode = parse_mode(mode)?;
    let static_renderers = match renderers {
        Some(dict) => build_renderers(dict)?,
        None => StaticRenderers::default(),
    };
    Ok((parsed_mode, static_renderers))
}

/// Convert Carve source to HTML.
///
/// With no `extensions`, this is the core renderer. Pass a list of extension
/// names to enable opt-in behavior. `mode` is `"interactive"` (default) or
/// `"static"`; `renderers` is an optional dict of build-time renderer callables
/// (keys `"mermaid"` / `"chart"` -> `(str) -> str`, `"math"` -> `(str, bool) ->
/// str`) consulted only on the static HTML path.
///
/// `symbols` is an optional `{name: value}` dict: a `:name:` symbol whose name
/// is in the map renders the mapped value, an unmapped one stays literal
/// `:name:` text.
///
/// SECURITY: a mapped symbol value is inserted as TRUSTED RAW output in the
/// target format - it is NOT escaped, the same trust class as the `renderers`
/// map. `symbols={"b": "<b>x</b>"}` emits a real `<b>` element. This is
/// deliberate: processor configuration is trusted. NEVER build a symbols map
/// out of untrusted / user-supplied input.
#[pyfunction]
#[pyo3(signature = (source, extensions = None, mode = "interactive", renderers = None, symbols = None, safe = false, profile = None, *, lowercase_heading_ids = None, positions = None, sections = None, source_lines = None, mention_url = None, tag_url = None, profile_base_host = None))]
#[allow(clippy::too_many_arguments)]
fn to_html(
    source: &str,
    extensions: Option<Vec<String>>,
    mode: &str,
    renderers: Option<Bound<'_, PyDict>>,
    symbols: Option<Bound<'_, PyDict>>,
    safe: bool,
    profile: Option<&str>,
    lowercase_heading_ids: Option<bool>,
    positions: Option<bool>,
    sections: Option<bool>,
    source_lines: Option<bool>,
    mention_url: Option<String>,
    tag_url: Option<String>,
    profile_base_host: Option<String>,
) -> PyResult<String> {
    let engine_options = EngineOptions {
        lowercase_heading_ids,
        positions,
        sections,
        source_lines,
        mention_url,
        tag_url,
        profile_base_host,
    };
    let (parsed_mode, static_renderers) = resolve_mode_and_renderers(mode, renderers.as_ref())?;
    let symbol_pairs = match symbols.as_ref() {
        Some(dict) => build_symbols(dict)?,
        None => Vec::new(),
    };
    // The fast no-options path only applies in interactive mode with no
    // renderers, no symbols and no extensions; anything else must go through
    // `render`.
    let names = extensions.unwrap_or_default();
    if names.is_empty()
        && parsed_mode == Mode::Interactive
        && symbol_pairs.is_empty()
        && static_renderers.diagrams.is_empty()
        && static_renderers.math.is_none()
        && !safe
        && profile.is_none()
        && engine_options == EngineOptions::default()
    {
        return Ok(carve_rs::to_html(source));
    }
    render(
        source,
        &names,
        parsed_mode,
        static_renderers,
        &symbol_pairs,
        safe,
        profile,
        engine_options,
        carve_rs::try_to_html_with_options,
    )
}

/// Convert Carve source to HTML with an explicit (required) extension list.
///
/// Supports the same `mode` / `renderers` / `symbols` keywords as [`to_html`]
/// (including the trusted-raw contract on symbol values).
#[pyfunction]
#[pyo3(signature = (source, extensions, mode = "interactive", renderers = None, symbols = None, safe = false, profile = None, *, lowercase_heading_ids = None, positions = None, sections = None, source_lines = None, mention_url = None, tag_url = None, profile_base_host = None))]
#[allow(clippy::too_many_arguments)]
fn to_html_with_extensions(
    source: &str,
    extensions: Vec<String>,
    mode: &str,
    renderers: Option<Bound<'_, PyDict>>,
    symbols: Option<Bound<'_, PyDict>>,
    safe: bool,
    profile: Option<&str>,
    lowercase_heading_ids: Option<bool>,
    positions: Option<bool>,
    sections: Option<bool>,
    source_lines: Option<bool>,
    mention_url: Option<String>,
    tag_url: Option<String>,
    profile_base_host: Option<String>,
) -> PyResult<String> {
    let (parsed_mode, static_renderers) = resolve_mode_and_renderers(mode, renderers.as_ref())?;
    let symbol_pairs = match symbols.as_ref() {
        Some(dict) => build_symbols(dict)?,
        None => Vec::new(),
    };
    render(
        source,
        &extensions,
        parsed_mode,
        static_renderers,
        &symbol_pairs,
        safe,
        profile,
        EngineOptions {
            lowercase_heading_ids,
            positions,
            sections,
            source_lines,
            mention_url,
            tag_url,
            profile_base_host,
        },
        carve_rs::try_to_html_with_options,
    )
}

/// True when no extensions were requested (None or empty list).
fn is_core(extensions: &Option<Vec<String>>) -> bool {
    extensions.as_ref().is_none_or(|v| v.is_empty())
}

/// Convert Carve source to Markdown.
#[pyfunction]
#[pyo3(signature = (source, extensions = None, profile = None))]
fn to_markdown(
    source: &str,
    extensions: Option<Vec<String>>,
    profile: Option<&str>,
) -> PyResult<String> {
    // The fast path must not swallow `profile`: returning here with a profile
    // set would accept the keyword and silently ignore it.
    if is_core(&extensions) && profile.is_none() {
        return Ok(carve_rs::to_markdown(source));
    }
    render(
        source,
        &extensions.unwrap_or_default(),
        Mode::Interactive,
        StaticRenderers::default(),
        &[],
        false,
        profile,
        EngineOptions::default(),
        carve_rs::try_to_markdown_with_options,
    )
}

/// Convert Carve source to plain text.
#[pyfunction]
#[pyo3(signature = (source, extensions = None, profile = None))]
fn to_plain_text(
    source: &str,
    extensions: Option<Vec<String>>,
    profile: Option<&str>,
) -> PyResult<String> {
    // The fast path must not swallow `profile`: returning here with a profile
    // set would accept the keyword and silently ignore it.
    if is_core(&extensions) && profile.is_none() {
        return Ok(carve_rs::to_plain_text(source));
    }
    render(
        source,
        &extensions.unwrap_or_default(),
        Mode::Interactive,
        StaticRenderers::default(),
        &[],
        false,
        profile,
        EngineOptions::default(),
        carve_rs::try_to_plain_text_with_options,
    )
}

/// Convert Carve source to ANSI-colored terminal text.
#[pyfunction]
#[pyo3(signature = (source, extensions = None, profile = None))]
fn to_ansi(
    source: &str,
    extensions: Option<Vec<String>>,
    profile: Option<&str>,
) -> PyResult<String> {
    // The fast path must not swallow `profile`: returning here with a profile
    // set would accept the keyword and silently ignore it.
    if is_core(&extensions) && profile.is_none() {
        return Ok(carve_rs::to_ansi(source));
    }
    render(
        source,
        &extensions.unwrap_or_default(),
        Mode::Interactive,
        StaticRenderers::default(),
        &[],
        false,
        profile,
        EngineOptions::default(),
        carve_rs::try_to_ansi_with_options,
    )
}

/// Read a document's provenance marker, as written by `carve fmt --stamp`.
///
/// Returns a dict `{"version": ..., "generated_by": ...}`, or None when the
/// document carries no marker - the normal case for a hand-written document,
/// meaning "unknown" rather than "current". `generated_by` is None when the
/// marker records no writer.
#[pyfunction]
fn read_stamp(py: Python<'_>, source: &str) -> PyResult<Option<Py<PyDict>>> {
    let Some(stamp) = carve_rs::read_stamp(source) else {
        return Ok(None);
    };

    let dict = PyDict::new(py);
    dict.set_item("version", stamp.version)?;
    dict.set_item("generated_by", stamp.generated_by)?;

    Ok(Some(dict.unbind()))
}

/// Whether a document was last processed under an older spec version than this
/// engine targets, so the `[behavior]` changelog entries between the two are
/// worth reviewing.
///
/// An unstamped document answers True: its provenance is unknown, and assuming
/// it is current is the unsafe direction. Pass `current_version` to compare
/// against something other than this engine's spec version.
#[pyfunction]
#[pyo3(signature = (source, current_version = None))]
fn needs_review(source: &str, current_version: Option<&str>) -> bool {
    carve_rs::needs_review(source, current_version.unwrap_or(carve_rs::SPEC_VERSION))
}

/// Parse Carve source and return its AST as a JSON string.
///
/// The PART 12 exchange shape, produced by the engine itself
/// (`carve_rs::to_json`) rather than by a walker written here - so this binding
/// publishes the same bytes as the CLI, carve-rb and every other consumer of
/// the same engine.
///
/// Positions are ON unless `positions=False` is passed. That is not the
/// engine's default - it is what this function has always done, and the AST
/// entry points are where a caller wants spans. Changing it would silently
/// remove `pos` from every existing caller's tree.
#[pyfunction]
#[pyo3(signature = (source, *, lowercase_heading_ids = None, positions = None, sections = None, source_lines = None, mention_url = None, tag_url = None, profile_base_host = None))]
#[allow(clippy::too_many_arguments)]
fn parse_json(
    source: &str,
    lowercase_heading_ids: Option<bool>,
    positions: Option<bool>,
    sections: Option<bool>,
    source_lines: Option<bool>,
    mention_url: Option<String>,
    tag_url: Option<String>,
    profile_base_host: Option<String>,
) -> String {
    let options = EngineOptions {
        lowercase_heading_ids,
        positions: Some(positions.unwrap_or(true)),
        sections,
        source_lines,
        mention_url,
        tag_url,
        profile_base_host,
    }
    .apply(Options::new());
    carve_rs::to_json(&carve_rs::parse_with_options(source, &options))
}

/// Parse Carve source and return its AST as Python data (dicts and lists).
///
/// The same tree as `parse_json`, decoded with the standard library's `json`
/// module so a caller does not have to. `parse_json` stays available for a
/// caller that wants to store or forward the bytes without a round trip
/// through Python objects.
#[pyfunction]
#[pyo3(signature = (source, *, lowercase_heading_ids = None, positions = None, sections = None, source_lines = None, mention_url = None, tag_url = None, profile_base_host = None))]
#[allow(clippy::too_many_arguments)]
fn parse(
    py: Python<'_>,
    source: &str,
    lowercase_heading_ids: Option<bool>,
    positions: Option<bool>,
    sections: Option<bool>,
    source_lines: Option<bool>,
    mention_url: Option<String>,
    tag_url: Option<String>,
    profile_base_host: Option<String>,
) -> PyResult<Py<PyAny>> {
    let json = py.import("json")?;
    let loaded = json.call_method1(
        "loads",
        (parse_json(
            source,
            lowercase_heading_ids,
            positions,
            sections,
            source_lines,
            mention_url,
            tag_url,
            profile_base_host,
        ),),
    )?;

    Ok(loaded.unbind())
}

/// Return the list of supported extension names.
///
/// Taken from the engine's registry, so a new extension in carve-rs is
/// reachable from Python as soon as the pin moves - no list here to update, and
/// none to forget.
#[pyfunction]
fn extensions() -> Vec<String> {
    supported()
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
    m.add_function(wrap_pyfunction!(read_stamp, m)?)?;
    m.add_function(wrap_pyfunction!(needs_review, m)?)?;
    m.add_function(wrap_pyfunction!(parse, m)?)?;
    m.add_function(wrap_pyfunction!(parse_json, m)?)?;
    Ok(())
}
