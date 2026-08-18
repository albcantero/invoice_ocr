"""Normaliza la salida (dict) del LLM a dataclasses tipadas."""
import datetime
import re
from dataclasses import dataclass, field

from ..extract import parse_amount_es


def _to_float(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    if "," in s:  # formato espanol "1.234,56"
        return parse_amount_es(s)
    s = re.sub(r"[^0-9.\-]", "", s)  # quita %, EUR, espacios
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_date(value):
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class LlmLine:
    description: "str | None" = None
    quantity: "float | None" = None
    price_unit: "float | None" = None
    tax_percent: "float | None" = None
    amount: "float | None" = None


@dataclass
class LlmInvoice:
    vendor_name: "str | None" = None
    vendor_vat: "str | None" = None
    invoice_date: "datetime.date | None" = None
    invoice_ref: "str | None" = None
    due_date: "datetime.date | None" = None
    currency: "str | None" = None
    lines: list = field(default_factory=list)
    amount_untaxed: "float | None" = None
    amount_tax: "float | None" = None
    amount_total: "float | None" = None


def normalize(raw):
    """dict crudo del LLM -> LlmInvoice. Nunca lanza; deja vacío lo que no case."""
    raw = raw or {}
    lines = []
    for item in (raw.get("lines") or []):
        if not isinstance(item, dict):
            continue
        lines.append(LlmLine(
            description=(item.get("description") or None),
            quantity=_to_float(item.get("quantity")),
            price_unit=_to_float(item.get("price_unit")),
            tax_percent=_to_float(item.get("tax_percent")),
            amount=_to_float(item.get("amount")),
        ))
    return LlmInvoice(
        vendor_name=(raw.get("vendor_name") or None),
        vendor_vat=(raw.get("vendor_vat") or None),
        invoice_date=_to_date(raw.get("invoice_date")),
        invoice_ref=(raw.get("invoice_ref") or None),
        due_date=_to_date(raw.get("due_date")),
        currency=(raw.get("currency") or None),
        lines=lines,
        amount_untaxed=_to_float(raw.get("amount_untaxed")),
        amount_tax=_to_float(raw.get("amount_tax")),
        amount_total=_to_float(raw.get("amount_total")),
    )
