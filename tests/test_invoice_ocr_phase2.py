import datetime

from odoo.tests import TransactionCase, tagged

from odoo.addons.invoice_ocr.lib.llm.schema import LlmInvoice, LlmLine


@tagged("post_install", "-at_install")
class TestInvoiceOcrPhase2(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {"name": "Proveedor Test", "vat": "ESB12345674"}
        )

    def _doc(self, raw_text):
        att = self.env["ir.attachment"].create({"name": "t.pdf", "raw": b""})
        return self.env["invoice.ocr.document"].create(
            {"name": "t.pdf", "attachment_id": att.id, "raw_text": raw_text}
        )

    def test_apply_llm_result_writes_lines_and_fills_gaps(self):
        raw_text = "CIF B12345674\nBASE IMPONIBLE 225,00\nIVA 21% 47,25\nTOTAL 272,25\n"
        doc = self._doc(raw_text)
        llm = LlmInvoice(
            vendor_name="Proveedor Test",
            vendor_vat=None,
            due_date=datetime.date(2026, 7, 14),
            lines=[LlmLine("Siega", 1.0, 25.0, 21.0, 25.0),
                   LlmLine("Taquear", 8.0, 25.0, 21.0, 200.0)],
        )
        doc._apply_llm_result(llm)
        self.assertEqual(len(doc.line_ids), 2)
        self.assertEqual(doc.line_ids[1].description, "Taquear")
        self.assertEqual(doc.line_ids[1].amount, 200.0)
        self.assertEqual(doc.due_date, datetime.date(2026, 7, 14))
        self.assertEqual(doc.partner_id, self.partner)   # casa por VAT de la heuristica
        self.assertEqual(doc.amount_total, 272.25)        # heuristica del raw_text
