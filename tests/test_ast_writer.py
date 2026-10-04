import json
import pytest
import carve


def test_ast_writer_escapes_literal_markup_and_preserves_text():
    text = '*literal text* [label](url)'
    ast = {'type': 'document', 'srcByteLength': 0, 'children': [
        {'type': 'paragraph', 'children': [{'type': 'text', 'value': text}]}
    ]}
    source = carve.render_ast_json(json.dumps(ast))
    assert carve.to_plain_text(source).strip() == text
    assert '<strong>' not in carve.to_html(source)
    assert '<a ' not in carve.to_html(source)
    assert carve.to_carve(source) == source


@pytest.mark.parametrize('source', [
    '{',
    '{"type":"document","srcByteLength":0,"children":[{"type":"bogus"}]}',
])
def test_ast_writer_rejects_invalid_interchange(source):
    with pytest.raises(ValueError):
        carve.render_ast_json(source)


def test_ast_writer_refuses_blank_table_rows_without_source_spelling():
    ast = {'type': 'document', 'srcByteLength': 0, 'children': [
        {'type': 'table', 'rows': [{'type': 'table_row', 'cells': [
            {'type': 'table_cell', 'header': False, 'children': []}
        ]}]}
    ]}
    with pytest.raises(ValueError, match='no Carve source spelling'):
        carve.render_ast_json(json.dumps(ast))
