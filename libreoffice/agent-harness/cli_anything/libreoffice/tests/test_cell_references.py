"""Cell addresses must use the same keys as the native exporters."""
import pytest

from cli_anything.libreoffice.core.calc import set_cell, get_cell, clear_cell
from cli_anything.libreoffice.core.document import create_document
from cli_anything.libreoffice.core.export import to_ods, _sheet_to_text, _sheet_to_html
from cli_anything.libreoffice.core.importer import import_odf


@pytest.mark.parametrize("ref", ["A01", " a001 ", "AA002"])
def test_padded_rows_use_canonical_keys(ref):
    project = create_document(doc_type="calc")
    expected = "AA2" if ref == "AA002" else "A1"
    result = set_cell(project, ref, "saved value")
    assert result["ref"] == expected
    assert get_cell(project, expected)["value"] == "saved value"
    set_cell(project, expected, "replacement")
    assert len(project["sheets"][0]["cells"]) == 1
    assert get_cell(project, ref)["value"] == "replacement"
    assert clear_cell(project, ref)["cleared"] is True
    assert project["sheets"][0]["cells"] == {}


@pytest.mark.parametrize("ref, canonical", [("A01", "A1"), (" a001 ", "A1"), ("aa002", "AA2")])
def test_padded_rows_survive_native_exports(tmp_path, ref, canonical):
    project = create_document(doc_type="calc")
    set_cell(project, ref, "saved value")
    sheet = project["sheets"][0]
    assert "saved value" in _sheet_to_text(sheet)
    assert "saved value" in _sheet_to_html(sheet)
    path = str(tmp_path / "padded.ods")
    to_ods(project, path)
    imported = import_odf(path)
    assert get_cell(imported, canonical)["value"] == "saved value"


@pytest.mark.parametrize("ref", ["\u00df1", "\u00c91", "\uff211", "A\u0661", "A\u00b2", "A\uff11"])
@pytest.mark.parametrize("operation", [set_cell, get_cell, clear_cell])
def test_non_ascii_addresses_rejected_without_mutation(ref, operation):
    project = create_document(doc_type="calc")
    args = (project, ref, "bad") if operation is set_cell else (project, ref)
    with pytest.raises(ValueError, match="Invalid cell reference"):
        operation(*args)
    assert project["sheets"][0]["cells"] == {}


@pytest.mark.parametrize("ref", ["A0", "A000", "1A", "A1B", "A-1", "A1.5", "", "A", "1"])
def test_invalid_ascii_addresses_still_rejected(ref):
    project = create_document(doc_type="calc")
    with pytest.raises(ValueError):
        set_cell(project, ref, "bad")
    assert project["sheets"][0]["cells"] == {}
