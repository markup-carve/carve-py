"""Export Docling's document model directly to Carve source and provenance."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .carve import render_ast_json, __version__


@dataclass
class DoclingExport:
    value: str
    ast: Dict[str, Any]
    diagnostics: List[Dict[str, Any]]
    provenance: List[Dict[str, Any]]
    assets: Dict[str, bytes] = field(default_factory=dict)
    source: Dict[str, Any] = field(default_factory=dict)
    versions: Dict[str, str] = field(default_factory=dict)
    assessment: str = "docling-carve-v1"
    complete: bool = False


class DoclingExportError(ValueError):
    def __init__(self, result: DoclingExport):
        self.result = result
        super().__init__("Docling export requires review of %d diagnostic(s)" % len(result.diagnostics))


def export_docling(document: Any, *, asset_dir: Optional[Path] = None,
                   asset_prefix: str = "assets", strict: bool = False,
                   max_table_cells: int = 100000, included_content_layers: Optional[Any] = None) -> DoclingExport:
    """Export headings, text, links, tables, and figures without Markdown.

    Images are returned as PNG bytes. Pass asset_dir to write them after strict
    checks pass; asset_prefix is their URL directory relative to the document.
    Requires the optional docling-core dependency on Python 3.10+.
    """
    try:
        from docling_core.types.doc import PictureItem, TableItem, TextItem, GroupItem, InlineGroup, CodeItem, FloatingItem, RichTableCell, ContentLayer
    except ImportError as exc:
        raise ImportError("Install carve-lang[docling] on Python 3.10+ to export Docling documents") from exc
    if isinstance(max_table_cells, bool) or not isinstance(max_table_cells, int) or max_table_cells < 1:
        raise ValueError("max_table_cells must be a positive integer")
    if asset_prefix.startswith(("/", "\\")) or ":" in asset_prefix or any(p == ".." for p in asset_prefix.replace("\\", "/").split("/")):
        raise ValueError("asset_prefix must be a relative URL directory")
    diagnostics: List[Dict[str, Any]] = []
    provenance: List[Dict[str, Any]] = []
    assets: Dict[str, bytes] = {}
    blocks: List[Dict[str, Any]] = []
    layers = {ContentLayer.BODY} if included_content_layers is None else {ContentLayer(layer) for layer in included_content_layers}
    items = list(document.iterate_items(with_groups=True, traverse_pictures=False, included_content_layers=layers))
    captions = {ref.cref for item, _ in items if isinstance(item, FloatingItem) for ref in item.captions}
    consumed = set(captions)
    for candidate, _ in items:
        if isinstance(candidate, TableItem):
            for cell in candidate.data.table_cells:
                if isinstance(cell, RichTableCell):
                    consumed.update(node.self_ref for node, _ in document.iterate_items(root=cell.ref.resolve(document), with_groups=True, traverse_pictures=False))

    def diagnostic(item: Any, code: str, message: str, path: Optional[str] = None) -> None:
        diagnostics.append({"code": code, "ref": item.self_ref, "path": path, "message": message})

    def text_nodes(item: Any, text: Optional[str] = None) -> List[Dict[str, Any]]:
        value = item.text if text is None else text
        normalized = re.sub(r"(?:(?:\r\n|[\r\n])[ \t]*){2,}", " ", value)
        if normalized != value:
            diagnostic(item, "text-linebreaks-normalized", "Blank lines inside one text item became spaces.")
        if not normalized:
            return []
        nodes = [{"type": "text", "value": normalized}]
        formatting = getattr(item, "formatting", None)
        if formatting:
            mapping = [("bold", "strong"), ("italic", "emphasis"), ("underline", "underline"),
                       ("strikethrough", "strike")]
            for key, kind in mapping:
                if getattr(formatting, key, False):
                    nodes = [{"type": kind, "children": nodes}]
            script = getattr(getattr(formatting, "script", None), "value", None)
            if script in ("sub", "super"):
                nodes = [{"type": "subscript" if script == "sub" else "superscript", "children": nodes}]
        link = getattr(item, "hyperlink", None)
        if link is not None:
            nodes = [{"type": "link", "href": str(link), "children": nodes}]
        return nodes

    def caption_nodes(item: Any) -> List[Dict[str, Any]]:
        nodes: List[Dict[str, Any]] = []
        for ref in item.captions:
            caption = ref.resolve(document)
            if nodes:
                nodes.append({"type": "text", "value": " "})
            value = re.sub(r"\r\n|[\r\n]", " ", caption.text)
            if value != caption.text:
                diagnostic(caption, "caption-linebreaks-normalized", "Caption line breaks became spaces in native source.")
            nodes.extend(text_nodes(caption, value))
        return nodes

    def table(item: Any, path: str) -> Optional[Dict[str, Any]]:
        data = item.data
        nr, nc = data.num_rows, data.num_cols
        if nr < 1 or nc < 1 or nr * nc > max_table_cells:
            raise ValueError("%s: table dimensions must be positive and within max_table_cells" % item.self_ref)
        grid: List[List[Optional[Dict[str, Any]]]] = [[None for _ in range(nc)] for _ in range(nr)]
        for cell in data.table_cells:
            r0, r1 = cell.start_row_offset_idx, cell.end_row_offset_idx
            c0, c1 = cell.start_col_offset_idx, cell.end_col_offset_idx
            if not (0 <= r0 < r1 <= nr and 0 <= c0 < c1 <= nc):
                raise ValueError("%s: cell is outside the table" % item.self_ref)
            if r1 - r0 != cell.row_span or c1 - c0 != cell.col_span:
                raise ValueError("%s: inconsistent cell span and offsets" % item.self_ref)
            value = cell.text
            cell_path = "%s/rows/%d/cells/%d" % (path, r0, c0)
            if isinstance(cell, RichTableCell):
                root = cell.ref.resolve(document)
                descendants = list(document.iterate_items(root=root, with_groups=True, traverse_pictures=False))
                consumed.update(node.self_ref for node, _ in descendants)
                value = " ".join(node.text for node, _ in descendants if isinstance(node, TextItem))
                for node, _ in descendants:
                    if isinstance(node, TextItem):
                        provenance.append({"path": cell_path, "ref": node.self_ref, "role": "rich-cell-text",
                                           "pages": [prov.model_dump(mode="json") for prov in node.prov]})
                diagnostic(item, "block-cell-flattened", "Rich cell blocks became inline text.", cell_path)
            if not value.strip() and (cell.row_span > 1 or cell.col_span > 1):
                value = "[empty]"
                diagnostic(item, "empty-merged-cell-placeholder", "An empty merged cell uses [empty] to retain its geometry in native source.", cell_path)
            if "\n" in value or "\r" in value:
                value = re.sub(r"\r\n|[\r\n]", " ", value)
                diagnostic(item, "cell-linebreaks-normalized", "Cell line breaks became spaces in native source.", cell_path)
            origin: Dict[str, Any] = {"type": "table_cell", "header": cell.column_header or cell.row_header,
                                      "children": [{"type": "text", "value": value}]}
            if cell.row_span > 1:
                origin["rowspan"] = cell.row_span
            if cell.col_span > 1:
                origin["colspan"] = cell.col_span
            if cell.row_section:
                diagnostic(item, "row-section-flattened", "Row-section role is not represented in source.", cell_path)
            if cell.fillable:
                diagnostic(item, "fillable-cell-flattened", "Fillable-cell behavior is not represented in source.", cell_path)
            for r in range(r0, r1):
                for c in range(c0, c1):
                    if grid[r][c] is not None:
                        raise ValueError("%s: overlapping table cells" % item.self_ref)
                    grid[r][c] = origin if (r, c) == (r0, c0) else {
                        "type": "table_cell", "header": False, "span": "colspan" if r == r0 else "rowspan", "children": []}
            if cell.bbox is not None:
                entry = {"path": cell_path, "ref": item.self_ref, "bbox": cell.bbox.model_dump(mode="json")}
                if len(item.prov) == 1:
                    entry["page_no"] = item.prov[0].page_no
                else:
                    diagnostic(item, "cell-page-ambiguous", "Cell bounding box has no unique page association.", cell_path)
                provenance.append(entry)
        caption = caption_nodes(item)
        rows = [{"type": "table_row", "cells": [cell if cell is not None else {
            "type": "table_cell", "header": False, "children": []} for cell in row]} for row in grid]
        retained = [index for index, row in enumerate(rows) if any(cell.get("span") or any(node.get("value", "").strip() for node in cell.get("children", [])) for cell in row["cells"])]
        if len(retained) != len(rows):
            for index in range(len(rows)):
                if index not in retained:
                    diagnostic(item, "blank-table-row-omitted", "Blank source row %d has no native Carve spelling and was omitted." % index, path if retained or caption else None)
            remap = {old: new for new, old in enumerate(retained)}
            for entry in provenance + diagnostics:
                entry_path = entry.get("path")
                if entry_path and entry_path.startswith(path + "/rows/"):
                    suffix = entry_path[len(path + "/rows/"):]
                    row, rest = suffix.split("/", 1)
                    entry["path"] = path + "/rows/%d/" % remap[int(row)] + rest if int(row) in remap else None
            rows = [rows[index] for index in retained]
        if not rows:
            return {"type": "paragraph", "children": caption} if caption else None
        return {"type": "table", "rows": rows, "caption": caption}

    for item, depth in items:
        if item.self_ref in consumed:
            continue
        if isinstance(item, GroupItem) and not isinstance(item, InlineGroup):
            if getattr(item, "meta", None):
                diagnostic(item, "metadata-not-exported", "Group metadata is not represented in source.")
            if item.self_ref != document.body.self_ref:
                diagnostic(item, "group-flattened", "Group nesting is flattened; children remain in reading order.")
            continue
        path = "/children/%d" % len(blocks)
        diagnostic_start = len(diagnostics)
        pages = [prov.model_dump(mode="json") for prov in getattr(item, "prov", [])]
        block: Optional[Dict[str, Any]] = None
        if isinstance(item, InlineGroup):
            runs = list(document.iterate_items(root=item, with_groups=True, traverse_pictures=False, included_content_layers=layers))
            consumed.update(child.self_ref for child, _ in runs if child.self_ref != item.self_ref)
            inline = []
            for child, _ in runs:
                if isinstance(child, TextItem):
                    inline.extend(text_nodes(child))
                    pages.extend(prov.model_dump(mode="json") for prov in getattr(child, "prov", []))
                    if child.label.value not in ("text", "paragraph", "caption"):
                        diagnostic(child, "inline-role-flattened", "Inline text role became a formatted text run.", path)
                elif not isinstance(child, GroupItem):
                    diagnostic(child, "inline-item-dropped", "Non-text inline item is not represented in the paragraph.", path)
            block = {"type": "paragraph", "children": inline} if inline else None
        elif isinstance(item, TableItem):
            block = table(item, path)
        elif isinstance(item, PictureItem):
            try:
                image = item.get_image(document)
            except (OSError, ValueError, KeyError, IndexError):
                image = None
            if image is None:
                diagnostic(item, "image-unavailable", "Figure image is unavailable; caption text remains.", path)
                block = {"type": "paragraph", "children": caption_nodes(item)}
            else:
                buffer = BytesIO()
                image.save(buffer, format="PNG")
                payload = buffer.getvalue()
                name = "figure-%s.png" % sha256(payload).hexdigest()[:24]
                assets[name] = payload
                caption = caption_nodes(item)
                alt = " ".join(re.sub(r"\r\n|[\r\n]", " ", ref.resolve(document).text) for ref in item.captions)
                target = {"type": "image", "src": asset_prefix.rstrip("/") + "/" + name if asset_prefix else name, "alt": alt}
                block = {"type": "figure", "target": target, "caption": caption} if caption else {"type": "paragraph", "children": [target]}
        elif isinstance(item, TextItem):
            label = item.label.value
            if label in ("title", "section_header"):
                level = getattr(item, "level", 1)
                if level > 6:
                    diagnostic(item, "heading-level-clamped", "Heading levels above six become level six.", path)
                block = {"type": "heading", "level": min(level, 6), "children": text_nodes(item)}
            elif label == "code":
                block = {"type": "code_block", "content": item.text, "lang": str(getattr(getattr(item, "code_language", None), "value", "") or "").lower()}
                if block["lang"] == "unknown":
                    block["lang"] = ""
                if isinstance(item, CodeItem) and item.captions:
                    block = {"type": "figure", "target": block, "caption": caption_nodes(item)}
            elif label == "formula" and not item.text.strip():
                diagnostic(item, "empty-formula-omitted", "Empty formula has no native math spelling and was omitted.")
            elif label == "formula":
                block = {"type": "paragraph", "children": [{"type": "math", "display": True, "content": item.text}]}
            else:
                block = {"type": "paragraph", "children": text_nodes(item)}
                if label not in ("text", "paragraph", "caption"):
                    diagnostic(item, "item-role-flattened", "%s role became a paragraph." % label, path)
        else:
            diagnostic(item, "unsupported-item", "Unsupported item %s; inspect its source reference." % type(item).__name__)
        if block is not None and block.get("type") in ("paragraph", "heading") and not block.get("children"):
            block = None
        if block is None:
            for entry in diagnostics[diagnostic_start:]:
                if entry.get("path") == path:
                    entry["path"] = None
        if block is not None:
            blocks.append(block)
            if isinstance(item, FloatingItem):
                for ref in item.captions:
                    caption_item = ref.resolve(document)
                    provenance.append({"path": path, "ref": caption_item.self_ref, "role": "caption",
                                       "pages": [prov.model_dump(mode="json") for prov in caption_item.prov]})
            provenance.append({"path": path, "ref": item.self_ref,
                               "pages": pages, "depth": depth})
        if isinstance(item, FloatingItem):
            for key in ("footnotes", "references"):
                if getattr(item, key, None):
                    diagnostic(item, "floating-association-not-exported", "%s associations are not represented in source." % key, path if block else None)
        for key in ("meta", "comments"):
            if getattr(item, key, None):
                diagnostic(item, "metadata-not-exported", "%s metadata is not represented in source." % key, path if block else None)

    ast = {"type": "document", "children": blocks, "srcByteLength": 0}
    value = render_ast_json(json.dumps(ast, ensure_ascii=False))
    result = DoclingExport(value=value, ast=ast, diagnostics=diagnostics, provenance=provenance, assets=assets,
                           source={"name": document.name, "origin": document.origin.model_dump(mode="json") if document.origin else None},
                           versions={"carve": __version__, "docling-core": version("docling-core")})
    if strict and diagnostics:
        raise DoclingExportError(result)
    if asset_dir is not None and assets:
        destination = Path(asset_dir)
        destination.mkdir(parents=True, exist_ok=True)
        for name, payload in assets.items():
            (destination / name).write_bytes(payload)
    return result
