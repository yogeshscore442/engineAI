"""Synthetic deterministic processing tests; never call providers."""
import pytest
from ai_engine.units import convert_value, convert_range_to_doc_unit
from ai_engine.summarize import build_summaries
from ai_engine.crosscheck import crosscheck_record
from ai_engine.brands import normalize_brand
from ai_engine.diagnoses import lookup_icd10


@pytest.mark.parametrize('name,unit1,unit2,value,expected', [
    ('glucose', 'mmol/L', 'mg/dL', 5, 90.091),
    ('creatinine', 'mg/dL', 'umol/L', 1, 88.4),
    ('hemoglobin', 'g/dL', 'g/L', 12, 120),
    ('unlisted', 'unit', 'other', 12, None),
])
def test_documented_conversion_factors(name, unit1, unit2, value, expected):
    result = convert_value(value, unit1, unit2, name)
    assert result == expected


def test_unknown_summary_is_not_all_normal_in_any_language():
    result = build_summaries({'tests': [{'name': 'Synthetic', 'flag': 'UNKNOWN', 'value': 5}], 'medicines': []}, use_llm=False)
    assert 'could not be classified' in result['summary_en']
    assert 'அனைத்து பரிசோதனை' not in result['summary_ta']
    assert 'सभी परीक्षण परिणाम सामान्य' not in result['summary_hi']


@pytest.mark.parametrize('flag', ['HIGH', 'LOW', 'NORMAL', 'UNKNOWN'])
def test_summaries_preserve_values_and_disclaimer(flag):
    result = build_summaries({'tests': [{'name': 'Synthetic', 'value': 5, 'unit': 'u', 'ref_low': 2, 'ref_high': 4, 'flag': flag}], 'medicines': [{'name_raw': 'Synthetic tablet'}]}, use_llm=False)
    assert '5 u' in result['summary_en']
    assert 'Synthetic tablet' in result['summary_en']
    assert 'not a diagnosis' in result['summary_en']
    assert result['summary_ta'] and result['summary_hi']


def test_crosscheck_flags_unmatched_items():
    record = {'tests': [{'value': 9876.5, 'confidence': 0.9}], 'medicines': [{'name_raw': 'InventedMedicine', 'confidence': 0.9}]}
    result = crosscheck_record(record, 'Synthetic report containing only unrelated text and no measurements.')
    assert set(result['needs_review']) == {'tests[0]', 'medicines[0]'}
    assert result['tests'][0]['confidence'] == 0.7


def test_unknown_terminology_stays_unknown():
    assert normalize_brand('zzzzunknown medicine') == (None, None)
    assert lookup_icd10('zzzzunknown condition') is None


def test_range_conversion_preserves_missing_bound():
    low, high, ok = convert_range_to_doc_unit(None, 10, 'g/dL', 'g/L', 'hemoglobin')
    assert (low, high, ok) == (None, 100, True)
