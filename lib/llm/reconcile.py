"""Fusiona el resultado determinista (heuristica) con el del LLM."""
import datetime
from dataclasses import dataclass, field


@dataclass
class MergedInvoice:
    partner_vat: "str | None" = None
    vendor_name: "str | None" = None
    invoice_date: "datetime.date | None" = None
    ref: "str | None" = None
    due_date: "datetime.date | None" = None
    amount_untaxed: "float | None" = None
    amount_tax: "float | None" = None
    amount_total: "float | None" = None
    lines: list = field(default_factory=list)


def _first(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def reconcile(heur, llm):
    """La heuristica gana en lo determinista; el LLM aporta lo difuso y huecos."""
    return MergedInvoice(
        partner_vat=_first(heur.partner_vat, llm.vendor_vat),
        vendor_name=llm.vendor_name,
        invoice_date=_first(heur.invoice_date, llm.invoice_date),
        ref=_first(heur.ref, llm.invoice_ref),
        due_date=llm.due_date,
        amount_untaxed=_first(heur.amount_untaxed, llm.amount_untaxed),
        amount_tax=_first(heur.amount_tax, llm.amount_tax),
        amount_total=_first(heur.amount_total, llm.amount_total),
        lines=list(llm.lines),
    )
