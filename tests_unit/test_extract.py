import datetime

from extract import (
    extract_invoice_fields,
    find_amounts,
    parse_amount_es,
    parse_date_es,
    parse_ref,
    parse_spanish_vat,
)


def test_parse_amount_es_thousands_and_decimals():
    assert parse_amount_es("1.234,56") == 1234.56


def test_parse_amount_es_simple_decimal():
    assert parse_amount_es("272,25") == 272.25


def test_parse_amount_es_with_currency_symbol():
    assert parse_amount_es("272,25 €") == 272.25


def test_parse_amount_es_integer_with_thousands():
    assert parse_amount_es("1.234") == 1234.0


def test_parse_amount_es_non_numeric_returns_none():
    assert parse_amount_es("abc") is None


def test_parse_amount_es_none_returns_none():
    assert parse_amount_es(None) is None


def test_parse_vat_nif():
    assert parse_spanish_vat("Cliente 12345678Z, gracias") == "12345678Z"


def test_parse_vat_cif_with_anchor():
    assert parse_spanish_vat("CIF: B12345674") == "B12345674"


def test_parse_vat_nie():
    assert parse_spanish_vat("NIE X1234567L") == "X1234567L"


def test_parse_vat_absent_returns_none():
    assert parse_spanish_vat("sin identificador fiscal") is None


def test_parse_date_slash_four_digit_year():
    assert parse_date_es("Fecha: 18/08/2026") == datetime.date(2026, 8, 18)


def test_parse_date_dash_two_digit_year():
    assert parse_date_es("01-02-26") == datetime.date(2026, 2, 1)


def test_parse_date_absent_returns_none():
    assert parse_date_es("sin fecha aqui") is None


def test_parse_date_glued_to_label():
    # El OCR suele pegar la etiqueta al valor sin espacio: "Fecha18/08/2026".
    assert parse_date_es("Fecha18/08/2026") == datetime.date(2026, 8, 18)


def test_parse_ref_factura_number():
    assert parse_ref("FACTURA Nº F-2026/45") == "F-2026/45"


def test_parse_ref_absent_returns_none():
    assert parse_ref("documento cualquiera") is None


def test_find_amounts_base_iva_total():
    text = "BASE IMPONIBLE 225,00\nIVA 21% 47,25\nTOTAL 272,25"
    amounts = find_amounts(text)
    assert amounts["base"] == 225.00
    assert amounts["iva"] == 47.25
    assert amounts["total"] == 272.25


def test_find_amounts_ignores_percentage_on_iva_line():
    assert find_amounts("IVA 21% 47,25")["iva"] == 47.25


def test_find_amounts_missing_returns_none():
    amounts = find_amounts("Gracias por su compra")
    assert amounts == {"base": None, "iva": None, "total": None}


def test_extract_invoice_fields_full_document():
    text = (
        "FACTURA Nº F-2026/45\n"
        "Fecha 18/08/2026\n"
        "CIF B12345674\n"
        "BASE IMPONIBLE 225,00\n"
        "IVA 21% 47,25\n"
        "TOTAL 272,25\n"
    )
    result = extract_invoice_fields(text)
    assert result.partner_vat == "B12345674"
    assert result.invoice_date == datetime.date(2026, 8, 18)
    assert result.ref == "F-2026/45"
    assert result.amount_untaxed == 225.00
    assert result.amount_tax == 47.25
    assert result.amount_total == 272.25
    assert result.amounts_consistent is True


def test_extract_invoice_fields_empty_text():
    result = extract_invoice_fields("")
    assert result.partner_vat is None
    assert result.amount_total is None
    assert result.amounts_consistent is False


def test_find_amounts_label_and_value_on_separate_lines():
    # Layout en columna: la etiqueta y el valor en líneas distintas.
    text = "Importe base\n225,00\nIVA 21%\n47,25\nTotal\n272,25"
    amounts = find_amounts(text)
    assert amounts["base"] == 225.00
    assert amounts["iva"] == 47.25
    assert amounts["total"] == 272.25


def test_parse_ref_prefers_invoice_code_near_factura():
    text = "Factura proforma INV/2026/00048\nOrigen\nPROY/2026/00008"
    assert parse_ref(text) == "INV/2026/00048"


# Texto OCR real de una proforma de Hermaflor (regresión del caso que falló).
_REAL_INVOICE_OCR = """HERMAFLORJARDINESYPLANTAS,S.L.
Factura proforma INV/2026/00048
NIF:07956918E
Fecha de factura
Fecha de vencimiento
Origen
13/07/2026
14/07/2026
PROY/2026/00008
Siega (Manual)
1,00 Horas
25,00
21% S
25,00
Taquear
8,00 Horas
25,00
21% S
200,00
Importe base
225,00
IVA 21%
47,25
Total
272,25
"""


def test_extract_real_invoice_ocr_text():
    result = extract_invoice_fields(_REAL_INVOICE_OCR)
    assert result.partner_vat == "07956918E"
    assert result.invoice_date == datetime.date(2026, 7, 13)
    assert result.ref == "INV/2026/00048"
    assert result.amount_untaxed == 225.00
    assert result.amount_tax == 47.25
    assert result.amount_total == 272.25
    assert result.amounts_consistent is True
