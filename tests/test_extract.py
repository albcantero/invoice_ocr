from lib.extract import parse_amount_es


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
