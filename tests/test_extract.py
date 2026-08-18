import datetime

from lib.extract import (
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


def test_parse_ref_factura_number():
    assert parse_ref("FACTURA Nº F-2026/45") == "F-2026/45"


def test_parse_ref_absent_returns_none():
    assert parse_ref("documento cualquiera") is None
