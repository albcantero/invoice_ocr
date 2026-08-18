import datetime

from lib.llm.schema import normalize, LlmInvoice

# Salida real del spike con qwen2.5:3b (numeros como strings en formato espanol)
RAW_3B = {
    "vendor_name": "HERMAFLORJARDINESYPLANTAS,S.L.",
    "vendor_vat": "07956918E",
    "invoice_date": "2026-07-13",
    "invoice_ref": "INV/2026/00048",
    "due_date": "2026-07-14",
    "currency": "EUR",
    "lines": [
        {"description": "Siega (Manual)", "quantity": "1,00", "price_unit": "25,00", "tax_percent": "21%", "amount": "25,00"},
        {"description": "Taquear", "quantity": "8,00", "price_unit": "25,00", "tax_percent": "21%", "amount": "200,00"},
    ],
    "amount_untaxed": "225,00", "amount_tax": "47,25", "amount_total": "272,25",
}

# Salida real del spike con qwen2.5:1.5b (numeros como floats, vat null)
RAW_15B = {
    "vendor_name": "HERMAFLORJARDINESYPLANTAS,S.L.",
    "vendor_vat": None,
    "invoice_date": "2026-07-13",
    "invoice_ref": "INV/2026/00048",
    "due_date": "2026-07-14",
    "currency": "EUR",
    "lines": [
        {"description": "Siega (Manual)", "quantity": 1, "price_unit": 25.0, "tax_percent": 21, "amount": 25.0},
        {"description": "Taquear", "quantity": 8, "price_unit": 25.0, "tax_percent": 21, "amount": 200.0},
    ],
    "amount_untaxed": 225.0, "amount_tax": 47.25, "amount_total": 272.25,
}


def test_normalize_3b_strings():
    inv = normalize(RAW_3B)
    assert isinstance(inv, LlmInvoice)
    assert inv.vendor_vat == "07956918E"
    assert inv.invoice_date == datetime.date(2026, 7, 13)
    assert inv.due_date == datetime.date(2026, 7, 14)
    assert inv.amount_total == 272.25
    assert len(inv.lines) == 2
    assert inv.lines[1].description == "Taquear"
    assert inv.lines[1].quantity == 8.0
    assert inv.lines[1].price_unit == 25.0
    assert inv.lines[1].tax_percent == 21.0
    assert inv.lines[1].amount == 200.0


def test_normalize_15b_floats_and_null_vat():
    inv = normalize(RAW_15B)
    assert inv.vendor_vat is None
    assert inv.amount_total == 272.25
    assert inv.lines[0].amount == 25.0
    assert inv.lines[1].tax_percent == 21.0


def test_normalize_empty():
    inv = normalize({})
    assert inv.lines == []
    assert inv.amount_total is None
