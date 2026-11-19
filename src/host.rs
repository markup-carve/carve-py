//! Native Python callbacks for the Carve 0.2 extension host.
use ::carve::api::{
    self, Channel, DocumentTransform, Extension, ExtensionDeclaration, RenderContext, Renderer,
    Tree,
};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyList, PyString};
use serde_json::Value;

fn engine_error(why: impl ToString) -> api::Error {
    api::Error::Option {
        option: "host".into(),
        message: why.to_string(),
    }
}

fn python_value(py: Python<'_>, value: &Value) -> PyResult<Py<PyAny>> {
    let json = py.import("json")?;
    Ok(json.call_method1("loads", (value.to_string(),))?.unbind())
}

fn json_value(value: &Bound<'_, PyAny>) -> PyResult<Value> {
    let json = value.py().import("json")?;
    let text: String = json.call_method1("dumps", (value,))?.extract()?;
    serde_json::from_str(&text).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

struct PythonRenderer(Py<PyAny>);
impl Renderer for PythonRenderer {
    fn render(&self, node: &Value, _cx: &RenderContext<'_>) -> Result<String, api::Error> {
        Python::attach(|py| {
            let arg = python_value(py, node).map_err(engine_error)?;
            let result = self.0.call1(py, (arg,)).map_err(engine_error)?;
            result.extract::<String>(py).map_err(engine_error)
        })
    }
}

struct PythonTransform(Py<PyAny>);
impl DocumentTransform for PythonTransform {
    fn transform(&self, view: Tree) -> Result<Tree, api::Error> {
        Python::attach(|py| {
            let value: Value =
                serde_json::from_str(&api::encode_tree(&view)).map_err(engine_error)?;
            let arg = python_value(py, &value).map_err(engine_error)?;
            let result = self.0.call1(py, (arg,)).map_err(engine_error)?;
            let next = json_value(result.bind(py)).map_err(engine_error)?;
            api::decode_tree(&next.to_string())
        })
    }
}

fn register(
    host: &mut api::Carve,
    name: String,
    renderers: Vec<(Channel, Box<dyn Renderer>)>,
    transform: Option<Box<dyn DocumentTransform>>,
) -> PyResult<()> {
    host.register_extension(Extension {
        declaration: ExtensionDeclaration {
            name,
            version: "1".into(),
            required: false,
            slots: Vec::new(),
        },
        renderers,
        transform,
    })
    .map_err(|e| super::CarveError::new_err(e.to_string()))
}

pub(super) fn render_host(
    py: Python<'_>,
    source: &str,
    tree: Option<&Bound<'_, PyAny>>,
    options: Option<&Bound<'_, PyDict>>,
    renderers: Option<&Bound<'_, PyDict>>,
    transforms: Option<&Bound<'_, PyList>>,
) -> PyResult<Py<PyAny>> {
    let mut host = api::Carve::new();
    let mut opts = api::Options::default();
    if let Some(options) = options {
        for (key, _) in options.iter() {
            let key: String = key.extract()?;
            if !matches!(key.as_str(), "mode" | "sections" | "rawHtml" | "extensions") {
                return Err(super::option_error(
                    py,
                    format!("native host does not read option {key}"),
                ));
            }
        }
        if let Some(mode) = options.get_item("mode")? {
            let mode: String = mode.extract()?;
            opts.mode = match mode.as_str() {
                "interactive" => api::Mode::Interactive,
                "static" => api::Mode::Static,
                _ => {
                    return Err(super::option_error(
                        py,
                        "mode must be interactive or static",
                    ))
                }
            };
        }
        if let Some(sections) = options.get_item("sections")? {
            opts.sections = sections.extract()?;
        }
        if let Some(raw) = options.get_item("rawHtml")? {
            opts.raw_html = raw.extract()?;
        }
        if let Some(standard) = options.get_item("extensions")? {
            for name in standard.extract::<Vec<String>>()? {
                host.enable_standard(&name, false)
                    .map_err(|e| super::CarveError::new_err(e.to_string()))?;
            }
        }
    }
    if let Some(renderers) = renderers {
        for (name, config) in renderers.iter() {
            let name: String = name.extract()?;
            let mut channels: Vec<(Channel, Box<dyn Renderer>)> = Vec::new();
            if config.is_callable() {
                let callback = config.unbind();
                channels.push((
                    Channel::Interactive,
                    Box::new(PythonRenderer(callback.clone_ref(py))),
                ));
                channels.push((Channel::BuildTime, Box::new(PythonRenderer(callback))));
            } else if let Ok(map) = config.cast::<PyDict>() {
                for (channel, callback) in map.iter() {
                    if !callback.is_callable() {
                        return Err(super::option_error(py, "renderer must be callable"));
                    }
                    let channel: String = channel.extract()?;
                    let selected = match channel.as_str() {
                        "interactive" => Channel::Interactive,
                        "static" | "build_time" => Channel::BuildTime,
                        _ => {
                            return Err(super::option_error(
                                py,
                                "renderer channel must be interactive or static",
                            ))
                        }
                    };
                    channels.push((selected, Box::new(PythonRenderer(callback.unbind()))));
                }
            } else if config.is_instance_of::<PyString>() {
                let selection: String = config.extract()?;
                if selection == "standard" {
                    host.enable_standard(&name, true)
                        .map_err(|e| super::CarveError::new_err(e.to_string()))?;
                    continue;
                }
                return Err(super::option_error(py, "renderer must be callable"));
            } else {
                return Err(super::option_error(py, "renderer must be callable"));
            }
            register(&mut host, name, channels, None)?;
        }
    }
    if let Some(transforms) = transforms {
        for (index, callback) in transforms.iter().enumerate() {
            if !callback.is_callable() {
                return Err(super::option_error(py, "transform must be callable"));
            }
            register(
                &mut host,
                format!("host.transform.{index}"),
                Vec::new(),
                Some(Box::new(PythonTransform(callback.unbind()))),
            )?;
        }
    }
    let rendered = if let Some(tree) = tree {
        let value = json_value(tree)?;
        let tree = api::decode_tree(&value.to_string())
            .map_err(|e| super::CarveError::new_err(e.to_string()))?;
        host.render_tree_with_diagnostics(&tree, &opts)
    } else {
        host.render_with_diagnostics(source, &opts)
    }
    .map_err(|e| super::CarveError::new_err(e.to_string()))?;
    let response = PyDict::new(py);
    response.set_item("html", rendered.html)?;
    response.set_item(
        "diagnostics",
        python_value(
            py,
            &serde_json::to_value(rendered.diagnostics)
                .map_err(engine_error)
                .map_err(|e| super::CarveError::new_err(e.to_string()))?,
        )?,
    )?;
    response.set_item("suppressedDiagnostics", rendered.suppressed_diagnostics)?;
    Ok(response.unbind().into_any())
}
