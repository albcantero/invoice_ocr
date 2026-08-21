import datetime

from lib.zonal.engine import extract_fields


def test_extract_fields_header():
    # palabras normalizadas: (x0, y0, x1, y1, texto). Las zonas excluyen la
    # etiqueta y encierran solo el valor.
    words = [
        (0.05, 0.05, 0.25, 0.08, "HERMAFLOR"),
        (0.05, 0.10, 0.14, 0.12, "CIF:"),
        (0.16, 0.10, 0.30, 0.12, "B12345674"),
        (0.05, 0.20, 0.18, 0.22, "Fecha"),
        (0.20, 0.20, 0.34, 0.22, "13/07/2026"),
        (0.60, 0.90, 0.72, 0.93, "Total"),
        (0.74, 0.90, 0.88, 0.93, "272,25"),
    ]
    zones = [
        {"field_key": "partner_vat", "x0": 0.15, "y0": 0.09, "x1": 0.35, "y1": 0.13},
        {"field_key": "invoice_date", "x0": 0.19, "y0": 0.19, "x1": 0.40, "y1": 0.23},
        {"field_key": "amount_total", "x0": 0.73, "y0": 0.88, "x1": 0.92, "y1": 0.95},
    ]
    result = extract_fields(words, zones)
    assert result["partner_vat"] == "B12345674"
    assert result["invoice_date"] == datetime.date(2026, 7, 13)
    assert result["amount_total"] == 272.25


def test_extract_fields_joins_multiple_words_in_zone():
    words = [
        (0.10, 0.10, 0.18, 0.12, "F-2026"),
        (0.18, 0.10, 0.24, 0.12, "/45"),
    ]
    zones = [{"field_key": "ref", "x0": 0.08, "y0": 0.09, "x1": 0.30, "y1": 0.13}]
    assert extract_fields(words, zones)["ref"] == "F-2026 /45"


def test_extract_fields_empty_zone_returns_none():
    words = [(0.1, 0.1, 0.2, 0.12, "algo")]
    zones = [{"field_key": "amount_total", "x0": 0.8, "y0": 0.8, "x1": 0.9, "y1": 0.9}]
    assert extract_fields(words, zones)["amount_total"] is None
