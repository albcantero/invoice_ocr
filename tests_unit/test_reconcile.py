import datetime

from lib.extract import ExtractedInvoice
from lib.llm.schema import LlmInvoice, LlmLine
from lib.llm.reconcile import reconcile


def test_heuristic_wins_vat_and_llm_provides_lines():
    heur = ExtractedInvoice(
        partner_vat="07956918E",
        invoice_date=datetime.date(2026, 7, 13),
        ref="INV/2026/00048",
        amount_untaxed=225.0, amount_tax=47.25, amount_total=272.25,
        amounts_consistent=True,
    )
    llm = LlmInvoice(
        vendor_name="HERMAFLOR",
        vendor_vat=None,  # el 1.5B lo falla
        due_date=datetime.date(2026, 7, 14),
        lines=[LlmLine("Siega", 1.0, 25.0, 21.0, 25.0),
               LlmLine("Taquear", 8.0, 25.0, 21.0, 200.0)],
        amount_total=272.25,
    )
    m = reconcile(heur, llm)
    assert m.partner_vat == "07956918E"          # heuristica manda (LLM lo falla)
    assert m.invoice_date == datetime.date(2026, 7, 13)
    assert m.ref == "INV/2026/00048"
    assert m.amount_total == 272.25
    assert m.vendor_name == "HERMAFLOR"          # solo LLM
    assert m.due_date == datetime.date(2026, 7, 14)
    assert len(m.lines) == 2


def test_llm_fills_heuristic_gaps():
    heur = ExtractedInvoice(partner_vat=None, invoice_date=None, ref=None,
                            amount_untaxed=None, amount_tax=None, amount_total=None)
    llm = LlmInvoice(vendor_vat="B12345674", invoice_date=datetime.date(2026, 1, 2),
                     invoice_ref="F-1", amount_total=100.0, lines=[])
    m = reconcile(heur, llm)
    assert m.partner_vat == "B12345674"          # heuristica vacia -> LLM rellena
    assert m.invoice_date == datetime.date(2026, 1, 2)
    assert m.ref == "F-1"
    assert m.amount_total == 100.0
