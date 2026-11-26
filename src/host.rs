//! Native Python callbacks for the Carve 0.2 extension host.
use ::carve::api::{
    self, Channel, DocumentTransform, Extension, ExtensionDeclaration, RenderContext, Renderer,
    Tree,
};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyList, PyString};
use serde_json::Value;

pub(super) fn has_configured_extensions(options: &Bound<'_, PyDict>) -> bool {
    options
        .get_item("extensions")
        .ok()
        .flatten()
        .and_then(|value| {
            value
                .cast::<PyList>()
                .ok()
                .map(|items| items.iter().any(|item| item.is_instance_of::<PyDict>()))
        })
        .unwrap_or(false)
}

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
    version: String,
    renderers: Vec<(Channel, Box<dyn Renderer>)>,
    transform: Option<Box<dyn DocumentTransform>>,
) -> PyResult<()> {
    host.register_extension(Extension {
        declaration: ExtensionDeclaration {
            name,
            version,
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
    let opts = if let Some(options) = options {
        let value = json_value(options.as_any())?;
        super::host_options::read(&value).map_err(|e| super::option_error(py, e))?
    } else {
        api::Options::default()
    };
    if let Some(options) = options {
        if let Some(standard) = options.get_item("extensions")? {
            let entries = standard
                .cast::<PyList>()
                .map_err(|_| super::option_error(py, "extensions must be a list"))?;
            for entry in entries.iter() {
                let (name, configured) = if let Ok(name) = entry.extract::<String>() {
                    (name, None)
                } else {
                    let row = entry.cast::<PyDict>().map_err(|_| {
                        super::option_error(
                            py,
                            "extension must be a name or an entry with name and options",
                        )
                    })?;
                    for (key, _) in row.iter() {
                        let key: String = key.extract()?;
                        if key != "name" && key != "options" {
                            return Err(super::option_error(
                                py,
                                format!("extension entry has unknown field {key}"),
                            ));
                        }
                    }
                    let name: String = row
                        .get_item("name")?
                        .ok_or_else(|| super::option_error(py, "extension entry needs name"))?
                        .extract()?;
                    let config = row.get_item("options")?.ok_or_else(|| {
                        super::option_error(py, format!("extension {name} needs options"))
                    })?;
                    let config = json_value(&config)?;
                    let config = config.as_object().cloned().ok_or_else(|| {
                        super::option_error(
                            py,
                            format!("extension {name} options must be an object"),
                        )
                    })?;
                    (name, Some(config))
                };
                let keyword = renderers.and_then(|items| items.get_item(&name).ok().flatten());
                let option = options.get_item("renderers")?.and_then(|value| {
                    value
                        .cast::<PyDict>()
                        .ok()
                        .and_then(|map| map.get_item(&name).ok().flatten())
                });
                let selection = keyword.or(option);
                let mut aria = false;
                let selected = if let Some(selection) = selection {
                    if selection.extract::<String>().ok().as_deref() == Some("standard") {
                        true
                    } else if let Ok(map) = selection.cast::<PyDict>() {
                        if let Some(standard) = map.get_item("standard")? {
                            if name == "carve.tabs" {
                                aria = standard
                                    .cast::<PyDict>()
                                    .ok()
                                    .and_then(|config| config.get_item("mode").ok().flatten())
                                    .and_then(|mode| mode.extract::<String>().ok())
                                    .as_deref()
                                    == Some("aria");
                            }
                            true
                        } else {
                            false
                        }
                    } else {
                        false
                    }
                } else {
                    false
                };
                if let Some(config) = configured.as_ref() {
                    super::standard_options::register(&mut host, &name, config, selected)
                        .map_err(|e| super::option_error(py, e))?;
                } else {
                    host.enable_standard(&name, selected)
                        .map_err(|e| super::CarveError::new_err(e.to_string()))?;
                }
                if aria {
                    host.enable_standard_tabs_renderer("aria")
                        .map_err(|e| super::CarveError::new_err(e.to_string()))?;
                }
            }
        }
    }
    let tree_value = tree.map(json_value).transpose()?;
    if let Some(renderers) = renderers {
        for (name, config) in renderers.iter() {
            let name: String = name.extract()?;
            let inferred = tree_value
                .as_ref()
                .and_then(|value| value.get("extensions"))
                .and_then(Value::as_array)
                .and_then(|rows| {
                    rows.iter()
                        .find(|row| row.get("name").and_then(Value::as_str) == Some(name.as_str()))
                })
                .and_then(|row| row.get("version"))
                .and_then(Value::as_str)
                .unwrap_or("1");
            let version = if let Ok(map) = config.cast::<PyDict>() {
                map.get_item("version")?
                    .map(|value| value.extract::<String>())
                    .transpose()?
                    .unwrap_or_else(|| inferred.to_string())
            } else {
                inferred.to_string()
            };
            let mut channels: Vec<(Channel, Box<dyn Renderer>)> = Vec::new();
            if config.is_callable() {
                let callback = config.unbind();
                channels.push((
                    Channel::Interactive,
                    Box::new(PythonRenderer(callback.clone_ref(py))),
                ));
                channels.push((Channel::BuildTime, Box::new(PythonRenderer(callback))));
            } else if let Ok(map) = config.cast::<PyDict>() {
                if map.get_item("standard")?.is_some() {
                    continue;
                }
                for (channel, callback) in map.iter() {
                    if channel.extract::<String>()? == "version" {
                        continue;
                    }
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
                    continue;
                }
                return Err(super::option_error(py, "renderer must be callable"));
            } else {
                return Err(super::option_error(py, "renderer must be callable"));
            }
            register(&mut host, name, version, channels, None)?;
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
                "1".into(),
                Vec::new(),
                Some(Box::new(PythonTransform(callback.unbind()))),
            )?;
        }
    }
    let rendered = if tree.is_some() {
        let value = tree_value.as_ref().expect("tree value parsed");
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
