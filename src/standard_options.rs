//! Configured standard extensions for the Python host path.
use ::carve::api::{self, extensions as ext};
use serde_json::{Map, Value};

fn field<'a>(
    map: &'a Map<String, Value>,
    camel: &str,
    snake: &str,
) -> Result<Option<&'a Value>, String> {
    if camel != snake && map.contains_key(camel) && map.contains_key(snake) {
        return Err(format!("option {camel} was given twice"));
    }
    Ok(map.get(camel).or_else(|| map.get(snake)))
}

fn keys(map: &Map<String, Value>, accepted: &[&str]) -> Result<(), String> {
    for key in map.keys() {
        if !accepted.contains(&key.as_str()) {
            return Err(format!("unknown option {key}"));
        }
    }
    Ok(())
}

fn string(map: &Map<String, Value>, camel: &str, snake: &str) -> Result<Option<String>, String> {
    field(map, camel, snake)?
        .map(|v| {
            v.as_str()
                .map(str::to_string)
                .ok_or_else(|| format!("option {camel} must be a string"))
        })
        .transpose()
}

fn boolean(map: &Map<String, Value>, camel: &str, snake: &str) -> Result<Option<bool>, String> {
    field(map, camel, snake)?
        .map(|v| {
            v.as_bool()
                .ok_or_else(|| format!("option {camel} must be a boolean"))
        })
        .transpose()
}

fn choice<'a>(
    map: &'a Map<String, Value>,
    camel: &str,
    snake: &str,
    accepted: &[&str],
) -> Result<Option<&'a str>, String> {
    let Some(value) = field(map, camel, snake)? else {
        return Ok(None);
    };
    let value = value
        .as_str()
        .ok_or_else(|| format!("option {camel} must be a string"))?;
    if !accepted.contains(&value) {
        return Err(format!("option {camel} has unknown value {value}"));
    }
    Ok(Some(value))
}

fn count(map: &Map<String, Value>, camel: &str, snake: &str) -> Result<Option<usize>, String> {
    field(map, camel, snake)?
        .map(|v| {
            v.as_u64()
                .and_then(|n| usize::try_from(n).ok())
                .ok_or_else(|| format!("option {camel} must be a nonnegative integer"))
        })
        .transpose()
}

fn small_count(map: &Map<String, Value>, camel: &str, snake: &str) -> Result<Option<u8>, String> {
    count(map, camel, snake)?
        .map(|value| u8::try_from(value).map_err(|_| format!("option {camel} is too large")))
        .transpose()
}

fn strings(
    map: &Map<String, Value>,
    camel: &str,
    snake: &str,
) -> Result<Option<Vec<String>>, String> {
    field(map, camel, snake)?
        .map(|value| {
            value
                .as_array()
                .ok_or_else(|| format!("option {camel} must be a list"))?
                .iter()
                .map(|item| {
                    item.as_str()
                        .map(str::to_string)
                        .ok_or_else(|| format!("option {camel} must contain strings"))
                })
                .collect()
        })
        .transpose()
}

fn optional_strings(
    map: &Map<String, Value>,
    camel: &str,
    snake: &str,
) -> Result<Option<Option<Vec<String>>>, String> {
    if field(map, camel, snake)?.is_some_and(Value::is_null) {
        return Ok(Some(None));
    }
    Ok(strings(map, camel, snake)?.map(Some))
}

fn levels(map: &Map<String, Value>) -> Result<Option<Vec<u8>>, String> {
    field(map, "levels", "levels")?
        .map(|value| {
            value
                .as_array()
                .ok_or("option levels must be a list".to_string())?
                .iter()
                .map(|item| {
                    item.as_u64()
                        .and_then(|n| u8::try_from(n).ok())
                        .ok_or("option levels must contain small nonnegative integers".to_string())
                })
                .collect()
        })
        .transpose()
}

pub(super) fn register(
    host: &mut api::Carve,
    name: &str,
    options: &Map<String, Value>,
    renderer: bool,
) -> Result<(), String> {
    let bundle = match name {
        "carve.externalLinks" => {
            keys(options, &["target", "rel", "nofollow"])?;
            let mut opts = ext::ExternalLinksOptions::default();
            if let Some(v) = string(options, "target", "target")? {
                opts.target = v;
            }
            if let Some(v) = string(options, "rel", "rel")? {
                opts.rel = v;
            }
            if let Some(v) = boolean(options, "nofollow", "nofollow")? {
                opts.nofollow = v;
            }
            Some(ext::external_links(opts))
        }
        "carve.headingLevelShift" => {
            keys(options, &["shift"])?;
            let mut opts = ext::HeadingLevelShiftOptions::default();
            if let Some(v) = small_count(options, "shift", "shift")? {
                opts.shift = v;
            }
            Some(ext::heading_level_shift(opts))
        }
        "carve.headingPermalinks" => {
            keys(
                options,
                &[
                    "symbol",
                    "cssClass",
                    "css_class",
                    "ariaLabel",
                    "aria_label",
                    "levels",
                    "prepend",
                    "showOnHover",
                    "show_on_hover",
                    "copyToClipboard",
                    "copy_to_clipboard",
                    "lowercaseIds",
                    "lowercase_ids",
                ],
            )?;
            let mut opts = ext::HeadingPermalinksOptions::default();
            if let Some(v) = string(options, "symbol", "symbol")? {
                opts.symbol = v;
            }
            if let Some(v) = string(options, "cssClass", "css_class")? {
                opts.css_class = v;
            }
            if let Some(v) = string(options, "ariaLabel", "aria_label")? {
                opts.aria_label = v;
            }
            if let Some(v) = levels(options)? {
                opts.levels = v;
            }
            if let Some(v) = boolean(options, "prepend", "prepend")? {
                opts.prepend = v;
            }
            if let Some(v) = boolean(options, "showOnHover", "show_on_hover")? {
                opts.show_on_hover = v;
            }
            if let Some(v) = boolean(options, "copyToClipboard", "copy_to_clipboard")? {
                opts.copy_to_clipboard = v;
            }
            if let Some(v) = boolean(options, "lowercaseIds", "lowercase_ids")? {
                opts.lowercase_ids = v;
            }
            Some(ext::heading_permalinks(opts))
        }
        "carve.headingNumbers" => {
            keys(options, &["minLevel", "min_level", "label", "crossref"])?;
            let mut opts = ext::HeadingNumbersOptions::default();
            if let Some(v) = small_count(options, "minLevel", "min_level")? {
                opts.min_level = v;
            }
            if let Some(v) = string(options, "label", "label")? {
                opts.label = v;
            }
            if let Some(v) = choice(
                options,
                "crossref",
                "crossref",
                &["number", "number-title", "numberTitle", "title"],
            )? {
                opts.crossref = match v {
                    "number" => ext::CrossrefStyle::Number,
                    "title" => ext::CrossrefStyle::Title,
                    _ => ext::CrossrefStyle::NumberTitle,
                };
            }
            Some(ext::heading_numbers(opts))
        }
        "carve.headingReference" => {
            keys(options, &["cssClass", "css_class"])?;
            let mut opts = ext::HeadingReferenceOptions::default();
            if let Some(v) = string(options, "cssClass", "css_class")? {
                opts.css_class = v;
            }
            Some(ext::heading_reference(opts))
        }
        "carve.toc" => {
            keys(
                options,
                &[
                    "minLevel",
                    "min_level",
                    "maxLevel",
                    "max_level",
                    "listType",
                    "list_type",
                    "cssClass",
                    "css_class",
                    "position",
                    "collapsible",
                    "summary",
                    "open",
                ],
            )?;
            let mut opts = ext::TableOfContentsOptions::default();
            if let Some(v) = small_count(options, "minLevel", "min_level")? {
                opts.min_level = v;
            }
            if let Some(v) = small_count(options, "maxLevel", "max_level")? {
                opts.max_level = v;
            }
            if let Some(v) = choice(options, "listType", "list_type", &["ul", "ol"])? {
                opts.list_type = if v == "ol" {
                    ext::ListType::Ol
                } else {
                    ext::ListType::Ul
                };
            }
            if let Some(v) = string(options, "cssClass", "css_class")? {
                opts.css_class = v;
            }
            if let Some(v) = choice(options, "position", "position", &["top", "bottom"])? {
                opts.position = if v == "bottom" {
                    ext::Position::Bottom
                } else {
                    ext::Position::Top
                };
            }
            if let Some(v) = boolean(options, "collapsible", "collapsible")? {
                opts.collapsible = v;
            }
            if let Some(v) = string(options, "summary", "summary")? {
                opts.summary = v;
            }
            if let Some(v) = boolean(options, "open", "open")? {
                opts.open = v;
            }
            Some(ext::table_of_contents(opts))
        }
        "carve.tocPlacement" => {
            keys(options, &[])?;
            Some(ext::toc_placement())
        }
        "carve.autolink" => {
            keys(options, &["allowedSchemes", "allowed_schemes"])?;
            let mut opts = ext::AutolinkOptions::default();
            if let Some(v) = strings(options, "allowedSchemes", "allowed_schemes")? {
                opts.allowed_schemes = v;
            }
            Some(ext::autolink(opts))
        }
        "carve.linkPolicy" => {
            keys(
                options,
                &[
                    "allowedSchemes",
                    "allowed_schemes",
                    "deniedSchemes",
                    "denied_schemes",
                    "allowedDomains",
                    "allowed_domains",
                    "deniedDomains",
                    "denied_domains",
                    "allowExternal",
                    "allow_external",
                    "allowInternal",
                    "allow_internal",
                    "rel",
                    "baseHost",
                    "base_host",
                ],
            )?;
            let mut opts = ext::LinkPolicyOptions::default();
            if let Some(v) = optional_strings(options, "allowedSchemes", "allowed_schemes")? {
                opts.allowed_schemes = v;
            }
            if let Some(v) = strings(options, "deniedSchemes", "denied_schemes")? {
                opts.denied_schemes = v;
            }
            if let Some(v) = optional_strings(options, "allowedDomains", "allowed_domains")? {
                opts.allowed_domains = v;
            }
            if let Some(v) = strings(options, "deniedDomains", "denied_domains")? {
                opts.denied_domains = v;
            }
            if let Some(v) = boolean(options, "allowExternal", "allow_external")? {
                opts.allow_external = v;
            }
            if let Some(v) = boolean(options, "allowInternal", "allow_internal")? {
                opts.allow_internal = v;
            }
            if let Some(v) = strings(options, "rel", "rel")? {
                opts.rel = v;
            }
            opts.base_host = string(options, "baseHost", "base_host")?;
            Some(ext::link_policy(opts))
        }
        "carve.wiki" => {
            keys(
                options,
                &["cssClass", "css_class", "newWindow", "new_window"],
            )?;
            let mut opts = ext::WikilinksOptions::default();
            opts.css_class = string(options, "cssClass", "css_class")?;
            if let Some(value) = boolean(options, "newWindow", "new_window")? {
                opts.new_window = value;
            }
            Some(ext::wikilinks(opts))
        }
        "carve.mathBlock" => {
            keys(options, &["language"])?;
            let mut opts = ext::MathBlockOptions::default();
            opts.language = string(options, "language", "language")?;
            Some(ext::math_block(opts))
        }
        "carve.codeGroup" => {
            keys(
                options,
                &[
                    "mode",
                    "wrapperClass",
                    "wrapper_class",
                    "panelClass",
                    "panel_class",
                    "labelClass",
                    "label_class",
                    "radioClass",
                    "radio_class",
                    "idPrefix",
                    "id_prefix",
                    "groupLabel",
                    "group_label",
                ],
            )?;
            let mut opts = ext::CodeGroupOptions::default();
            if let Some(mode) = choice(options, "mode", "mode", &["css", "aria"])? {
                opts.mode = if mode == "aria" {
                    ext::CodeGroupMode::Aria
                } else {
                    ext::CodeGroupMode::Css
                };
            }
            opts.wrapper_class = string(options, "wrapperClass", "wrapper_class")?;
            opts.panel_class = string(options, "panelClass", "panel_class")?;
            opts.label_class = string(options, "labelClass", "label_class")?;
            opts.radio_class = string(options, "radioClass", "radio_class")?;
            opts.id_prefix = string(options, "idPrefix", "id_prefix")?;
            opts.group_label = string(options, "groupLabel", "group_label")?;
            Some(ext::code_group(opts))
        }
        "carve.colorSwatch" => {
            keys(options, &["position", "shape", "tint", "reveal"])?;
            let mut opts = ext::ColorSwatchOptions::default();
            if let Some(position) = choice(
                options,
                "position",
                "position",
                &["before", "after", "none"],
            )? {
                opts.position = match position {
                    "after" => ext::SwatchPosition::After,
                    "none" => ext::SwatchPosition::None,
                    _ => ext::SwatchPosition::Before,
                };
            }
            if let Some(shape) = choice(options, "shape", "shape", &["square", "round", "ring"])? {
                opts.shape = match shape {
                    "round" => ext::SwatchShape::Round,
                    "ring" => ext::SwatchShape::Ring,
                    _ => ext::SwatchShape::Square,
                };
            }
            if let Some(v) = boolean(options, "tint", "tint")? {
                opts.tint = v;
            }
            if let Some(v) = boolean(options, "reveal", "reveal")? {
                opts.reveal = v;
            }
            Some(ext::color_swatch(opts))
        }
        "carve.references" => {
            keys(options, &["mode", "bibliography"])?;
            let mut opts = ext::CitationsOptions::default();
            if let Some(mode) = choice(
                options,
                "mode",
                "mode",
                &["numbered", "author-date", "authorDate"],
            )? {
                opts.mode = if mode == "numbered" {
                    ext::CitationMode::Numbered
                } else {
                    ext::CitationMode::AuthorDate
                };
            }
            if let Some(value) = options.get("bibliography") {
                opts.bibliography = Some(
                    value
                        .as_array()
                        .ok_or("option bibliography must be a list")?
                        .clone(),
                );
            }
            Some(ext::citations(opts))
        }
        "carve.index" => {
            keys(options, &["backrefLabel", "backref_label"])?;
            let mut opts = ext::IndexOptions::default();
            opts.backref_label = string(options, "backrefLabel", "backref_label")?;
            Some(ext::index(opts))
        }
        "carve.smartQuotes" => {
            keys(
                options,
                &[
                    "locale",
                    "openDoubleQuote",
                    "open_double_quote",
                    "closeDoubleQuote",
                    "close_double_quote",
                    "openSingleQuote",
                    "open_single_quote",
                    "closeSingleQuote",
                    "close_single_quote",
                ],
            )?;
            let opts = ext::SmartQuotesOptions {
                locale: string(options, "locale", "locale")?,
                open_double_quote: string(options, "openDoubleQuote", "open_double_quote")?,
                close_double_quote: string(options, "closeDoubleQuote", "close_double_quote")?,
                open_single_quote: string(options, "openSingleQuote", "open_single_quote")?,
                close_single_quote: string(options, "closeSingleQuote", "close_single_quote")?,
            };
            Some(ext::smart_quotes(&opts))
        }
        "carve.tabNormalize" => {
            keys(options, &["width"])?;
            Some(
                ext::tab_normalize(count(options, "width", "width")?.unwrap_or(2))
                    .map_err(|e| e.to_string())?,
            )
        }
        "carve.fencedRender.abc"
        | "carve.fencedRender.chart"
        | "carve.fencedRender.d2"
        | "carve.fencedRender.graphviz"
        | "carve.fencedRender.mermaid"
        | "carve.fencedRender.plantuml"
        | "carve.fencedRender.vega-lite"
        | "carve.fencedRender.wavedrom" => {
            keys(
                options,
                &[
                    "cssClass",
                    "css_class",
                    "tag",
                    "wrapInFigure",
                    "wrap_in_figure",
                    "figureClass",
                    "figure_class",
                    "label",
                ],
            )?;
            let mut opts = ext::PresetOptions::default();
            opts.css_class = string(options, "cssClass", "css_class")?;
            opts.tag = choice(options, "tag", "tag", &["pre", "div"])?.map(|v| {
                if v == "div" {
                    ext::Tag::Div
                } else {
                    ext::Tag::Pre
                }
            });
            if let Some(v) = boolean(options, "wrapInFigure", "wrap_in_figure")? {
                opts.wrap_in_figure = v;
            }
            opts.figure_class = string(options, "figureClass", "figure_class")?;
            opts.label = string(options, "label", "label")?;
            Some(match name {
                "carve.fencedRender.abc" => ext::abc(opts),
                "carve.fencedRender.chart" => ext::chart(opts),
                "carve.fencedRender.d2" => ext::d2(opts),
                "carve.fencedRender.graphviz" => ext::graphviz(opts),
                "carve.fencedRender.mermaid" => ext::mermaid(opts),
                "carve.fencedRender.plantuml" => ext::plantuml(opts),
                "carve.fencedRender.vega-lite" => ext::vega_lite(opts),
                _ => ext::wavedrom(opts),
            })
        }
        _ => {
            keys(options, &[])?;
            None
        }
    };
    if let Some(bundle) = bundle {
        host.register(if renderer {
            bundle
        } else {
            bundle.without_renderers()
        })
        .map_err(|e| e.to_string())
    } else {
        host.enable_standard(name, renderer)
            .map_err(|e| e.to_string())
    }
    .map_err(|e| format!("extension {name}: {e}"))
}
