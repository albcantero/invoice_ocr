from odoo import _, fields, models
from odoo.exceptions import UserError

from ..lib import extract as extract_lib
from ..lib.llm import reconcile as reconcile_lib


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
    line_ids = fields.One2many(
        "invoice.ocr.document.line", "document_id", string="Lines"
    )
    due_date = fields.Date(string="Due date")
    partner_name = fields.Char(string="Vendor name (raw)")
    llm_state = fields.Selection(
        [
            ("none", "None"),
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        default="none",
        required=True,
        index=True,
    )
    llm_error = fields.Text(string="LLM error")

    # --- OCR + extracción ---

    def _ocr_text(self):
        self.ensure_one()
        from ..lib import ocr as ocr_lib

        return ocr_lib.file_to_text(self.attachment_id.raw, self.attachment_id.mimetype)

    def _get_llm_backend(self):
        from ..lib.llm import factory as llm_factory
        params = self.env["ir.config_parameter"].sudo()
        return llm_factory.get_backend(
            backend=params.get_param("invoice_ocr.llm_backend", "embedded"),
            model=params.get_param("invoice_ocr.llm_model", "fast"),
            models_dir=params.get_param("invoice_ocr.llm_models_dir", ""),
            ollama_url=params.get_param("invoice_ocr.llm_ollama_url", "http://127.0.0.1:11434"),
        )

    def _cron_llm_enrichment(self, limit=20):
        if not self.env["ir.config_parameter"].sudo().get_param("invoice_ocr.llm_enabled"):
            return
        from ..lib.llm import schema as schema_lib
        docs = self.search([("llm_state", "=", "pending")], limit=limit)
        if not docs:
            return
        backend = docs[:1]._get_llm_backend()
        try:
            for document in docs:
                try:
                    document.llm_state = "processing"
                    raw = backend.extract_invoice_json(document.raw_text or "")
                    document._apply_llm_result(schema_lib.normalize(raw))
                    document.llm_state = "done"
                except Exception as error:  # noqa: BLE001
                    document.llm_state = "error"
                    document.llm_error = str(error)
                self.env.cr.commit()
        finally:
            backend.close()

    def action_process(self):
        llm_enabled = self.env["ir.config_parameter"].sudo().get_param(
            "invoice_ocr.llm_enabled"
        )
        for document in self:
            try:
                document.state = "processing"
                text = document._ocr_text()
                document._apply_extraction(text)
                if llm_enabled:
                    document.llm_state = "pending"
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

    def _apply_llm_result(self, llm_invoice):
        self.ensure_one()
        heur = extract_lib.extract_invoice_fields(self.raw_text or "")
        merged = reconcile_lib.reconcile(heur, llm_invoice)
        self.line_ids.unlink()
        vals = {
            "due_date": merged.due_date,
            "partner_name": merged.vendor_name,
            "partner_vat": merged.partner_vat,
            "invoice_date": merged.invoice_date,
            "ref": merged.ref,
            "amount_untaxed": merged.amount_untaxed or 0.0,
            "amount_tax": merged.amount_tax or 0.0,
            "amount_total": merged.amount_total or 0.0,
            "line_ids": [
                (0, 0, {
                    "sequence": (index + 1) * 10,
                    "description": line.description,
                    "quantity": line.quantity or 0.0,
                    "price_unit": line.price_unit or 0.0,
                    "tax_percent": line.tax_percent or 0.0,
                    "amount": line.amount or 0.0,
                })
                for index, line in enumerate(merged.lines)
            ],
        }
        partner = self.env["res.partner"]
        if merged.partner_vat:
            partner = self._match_partner(merged.partner_vat)
        if not partner and merged.vendor_name:
            partner = self.env["res.partner"].search(
                [("name", "=", merged.vendor_name)], limit=1
            )
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

    def _lines_match_total(self):
        self.ensure_one()
        if not self.amount_untaxed:
            return True  # sin base heuristica con que contrastar: se confia en las lineas
        lines_sum = sum(line.amount for line in self.line_ids)
        return abs(lines_sum - self.amount_untaxed) <= 0.05

    def _prepare_bill_vals(self):
        self.ensure_one()
        if self.line_ids and self._lines_match_total():
            line_cmds = [
                (0, 0, self._prepare_bill_line_vals_from_line(line))
                for line in self.line_ids
            ]
        else:
            line_cmds = [(0, 0, self._prepare_bill_line_vals())]
        return {
            "move_type": "in_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": self.invoice_date,
            "invoice_date_due": self.due_date,
            "ref": self.ref,
            "invoice_line_ids": line_cmds,
        }

    def _prepare_bill_line_vals_from_line(self, line):
        self.ensure_one()
        vals = {
            "name": line.description or _("Line"),
            "quantity": line.quantity or 1.0,
            "price_unit": line.price_unit or 0.0,
        }
        if line.product_id:
            vals["product_id"] = line.product_id.id
        tax = self.env["account.tax"].search([
            ("type_tax_use", "=", "purchase"),
            ("amount", "=", line.tax_percent or 21.0),
            ("company_id", "=", self.env.company.id),
        ], limit=1)
        if tax:
            vals["tax_ids"] = [(6, 0, tax.ids)]
        return vals

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
