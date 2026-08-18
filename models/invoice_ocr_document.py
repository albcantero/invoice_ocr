from odoo import _, fields, models
from odoo.exceptions import UserError

from ..lib import extract as extract_lib


class InvoiceOcrDocument(models.Model):
    _name = "invoice.ocr.document"
    _description = "Invoice OCR Document"
    _order = "create_date desc"

    name = fields.Char(string="File name", required=True)
    attachment_id = fields.Many2one(
        "ir.attachment", string="File", required=True, ondelete="cascade"
    )
    document_type = fields.Selection(
        [("invoice", "Vendor Bill")], string="Type", default="invoice", required=True
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("processing", "Processing"),
            ("to_review", "To Review"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        default="new",
        required=True,
        index=True,
    )
    partner_id = fields.Many2one("res.partner", string="Vendor")
    partner_vat = fields.Char(string="VAT (raw)")
    invoice_date = fields.Date(string="Invoice date")
    ref = fields.Char(string="Bill reference")
    amount_untaxed = fields.Monetary(string="Untaxed")
    amount_tax = fields.Monetary(string="Tax")
    amount_total = fields.Monetary(string="Total")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    raw_text = fields.Text(string="OCR text")
    move_id = fields.Many2one("account.move", string="Vendor bill", readonly=True)
    error_message = fields.Text(string="Error")

    # --- OCR + extracción ---

    def _ocr_text(self):
        self.ensure_one()
        from ..lib import ocr as ocr_lib

        return ocr_lib.file_to_text(self.attachment_id.raw, self.attachment_id.mimetype)

    def action_process(self):
        for document in self:
            try:
                document.state = "processing"
                text = document._ocr_text()
                document._apply_extraction(text)
            except Exception as error:  # noqa: BLE001 - se refleja en el registro
                document.state = "error"
                document.error_message = str(error)
        return True

    @staticmethod
    def _normalize_vat(vat):
        return (vat or "").replace(" ", "").replace(".", "").replace("-", "").upper()

    def _match_partner(self, vat):
        Partner = self.env["res.partner"]
        norm = self._normalize_vat(vat)
        if not norm:
            return Partner
        candidates = [norm, "ES" + norm]
        partner = Partner.search([("vat", "in", candidates)], limit=1)
        if partner:
            return partner
        return Partner.search([("vat", "=like", "%" + norm)], limit=1)

    def _apply_extraction(self, text):
        self.ensure_one()
        result = extract_lib.extract_invoice_fields(text or "")
        vals = {
            "raw_text": text,
            "partner_vat": result.partner_vat,
            "invoice_date": result.invoice_date,
            "ref": result.ref,
            "amount_untaxed": result.amount_untaxed or 0.0,
            "amount_tax": result.amount_tax or 0.0,
            "amount_total": result.amount_total or 0.0,
            "state": "to_review",
        }
        if result.partner_vat:
            partner = self._match_partner(result.partner_vat)
            if partner:
                vals["partner_id"] = partner.id
        self.write(vals)

    # --- Creación de la factura ---

    def _default_purchase_tax(self):
        return self.env["account.tax"].search(
            [
                ("type_tax_use", "=", "purchase"),
                ("amount", "=", 21.0),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )

    def _prepare_bill_line_vals(self):
        self.ensure_one()
        tax = self._default_purchase_tax()
        vals = {
            "name": self.name or _("Scanned invoice"),
            "quantity": 1.0,
            "price_unit": self.amount_untaxed or self.amount_total or 0.0,
        }
        if tax and self.amount_untaxed:
            vals["tax_ids"] = [(6, 0, tax.ids)]
        else:
            vals["price_unit"] = self.amount_total or vals["price_unit"]
        return vals

    def _prepare_bill_vals(self):
        self.ensure_one()
        return {
            "move_type": "in_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": self.invoice_date,
            "ref": self.ref,
            "invoice_line_ids": [(0, 0, self._prepare_bill_line_vals())],
        }

    def action_create_bill(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Indica un proveedor antes de crear la factura."))
        move = self.env["account.move"].create(self._prepare_bill_vals())
        self.write({"move_id": move.id, "state": "done"})
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
        }
