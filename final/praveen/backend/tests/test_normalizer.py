"""
tests/test_normalizer.py — Unit tests for normalizer and catalog lookup.
"""
from app.services.normalizer import normalize_date, normalize_unit, normalize_test
from app.catalog.test_catalog import lookup


def test_normalize_date_dmy():
    assert normalize_date("15/06/2024") == "2024-06-15"


def test_normalize_date_already_iso():
    assert normalize_date("2024-06-15") == "2024-06-15"


def test_normalize_date_with_month_name():
    assert normalize_date("15 Jun 2024") == "2024-06-15"


def test_normalize_date_none():
    assert normalize_date(None) is None


def test_normalize_date_unparsable():
    result = normalize_date("not-a-date")
    assert result is None


def test_normalize_unit_lowercase():
    assert normalize_unit("mg/dl") == "mg/dL"
    assert normalize_unit("g/dl") == "g/dL"
    assert normalize_unit("miu/l") == "mIU/L"


def test_normalize_unit_unknown():
    result = normalize_unit("furlong/fortnight")
    assert result == "furlong/fortnight"  # unknown units returned as-is


def test_catalog_hba1c_lookup():
    entry = lookup("HbA1c")
    assert entry is not None
    assert entry.canonical == "HbA1c"
    assert entry.loinc == "4548-4"


def test_catalog_alias_lookup():
    entry = lookup("glycated hemoglobin")
    assert entry is not None
    assert entry.canonical == "HbA1c"


def test_catalog_case_insensitive():
    entry = lookup("HAEMOGLOBIN")
    assert entry is not None
    assert entry.canonical == "Haemoglobin"


def test_catalog_unknown_test():
    assert lookup("totally_unknown_test_xyz") is None


def test_normalize_test_adds_canonical():
    test_dict = {"name": "HbA1c", "value": 6.5, "unit": "%"}
    result = normalize_test(test_dict)
    assert result["name_canonical"] == "HbA1c"
    assert result["loinc"] == "4548-4"


def test_normalize_test_preserves_extra_keys():
    test_dict = {"name": "HbA1c", "value": 6.5, "custom_field": "extra"}
    result = normalize_test(test_dict)
    assert result["custom_field"] == "extra"


def test_normalize_test_fills_missing_ref_range():
    test_dict = {"name": "TSH", "value": 3.0, "unit": "mIU/L"}
    result = normalize_test(test_dict)
    assert result["ref_low"] is not None
    assert result["ref_high"] is not None


def test_missing_unit_does_not_invent_reference_range():
    result = normalize_test({"name": "TSH", "value": 3.0})
    assert result['unit'] is None
    assert result['flag'] == 'UNKNOWN'


def test_one_sided_document_range_is_preserved():
    result = normalize_test({'name': 'TSH', 'value': 0.1, 'unit': 'mIU/L', 'ref_high': 4})
    assert result.get('ref_low') is None
    assert result['ref_high'] == 4


def test_invalid_calendar_date_is_rejected():
    assert normalize_date('2026-02-30') is None
    assert normalize_date(123) is None
