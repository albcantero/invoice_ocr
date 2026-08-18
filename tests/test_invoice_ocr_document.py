from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInvoiceOcrDocument(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {"name": "Proveedor Test", "vat": "ESB12345674"}
        )

    def _new_document(self):
        attachment = self.env["ir.attachment"].create({"name": "t.pdf", "raw": b""})
        return self.env["invoice.ocr.document"].create(
            {"name": "t.pdf", "attachment_id": attachment.id}
        )

    def test_apply_extraction_maps_fields_and_matches_partner(self):
        text = (
            "FACTURA Nº F-2026/45\nFecha 18/08/2026\nCIF B12345674\n"
            "BASE IMPONIBLE 225,00\nIVA 21% 47,25\nTOTAL 272,25\n"
        )
        doc = self._new_document()
        doc._apply_extraction(text)
        self.assertEqual(doc.state, "to_review")
        self.assertEqual(doc.ref, "F-2026/45")
        self.assertEqual(doc.amount_untaxed, 225.00)
        self.assertEqual(doc.amount_tax, 47.25)
        self.assertEqual(doc.amount_total, 272.25)
        self.assertEqual(doc.partner_id, self.partner)

    def test_create_bill_from_reviewed_document(self):
        text = "CIF B12345674\nBASE IMPONIBLE 225,00\nIVA 21% 47,25\nTOTAL 272,25\n"
        doc = self._new_document()
        doc._apply_extraction(text)
        doc.action_create_bill()
        self.assertEqual(doc.state, "done")
        self.assertTrue(doc.move_id)
        self.assertEqual(doc.move_id.move_type, "in_invoice")
        self.assertEqual(doc.move_id.state, "draft")
        self.assertEqual(doc.move_id.partner_id, self.partner)
