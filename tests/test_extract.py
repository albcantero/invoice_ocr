from lib.extract import parse_amount_es, parse_spanish_vat


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
