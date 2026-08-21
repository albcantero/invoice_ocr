from odoo import fields, models

FIELD_KEYS = [
    ("partner_vat", "CIF / NIF"),
    ("invoice_date", "Fecha"),
    ("ref", "Nº factura"),
    ("amount_untaxed", "Base"),
    ("amount_tax", "IVA"),
    ("amount_total", "Total"),
]


class InvoiceOcrTemplate(models.Model):
    _name = "invoice.ocr.template"
    _description = "Invoice OCR Template"
    _order = "partner_id, name"

    name = fields.Char(required=True)
    partner_id = fields.Many2one(
        "res.partner", string="Vendor", required=True, index=True
    )
    active = fields.Boolean(default=True)
    zone_ids = fields.One2many(
        "invoice.ocr.template.zone", "template_id", string="Zones"
    )


class InvoiceOcrTemplateZone(models.Model):
    _name = "invoice.ocr.template.zone"
    _description = "Invoice OCR Template Zone"
    _order = "template_id, field_key"

    template_id = fields.Many2one(
        "invoice.ocr.template", required=True, ondelete="cascade"
    )
    field_key = fields.Selection(FIELD_KEYS, string="Field", required=True)
    x0 = fields.Float(digits=(12, 6))
    y0 = fields.Float(digits=(12, 6))
    x1 = fields.Float(digits=(12, 6))
    y1 = fields.Float(digits=(12, 6))
