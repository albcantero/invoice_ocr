from odoo import fields, models


class InvoiceOcrDocumentLine(models.Model):
    _name = "invoice.ocr.document.line"
    _description = "Invoice OCR Document Line"
    _order = "document_id, sequence, id"

    document_id = fields.Many2one(
        "invoice.ocr.document", required=True, ondelete="cascade"
    )
    sequence = fields.Integer(default=10)
    description = fields.Char()
    quantity = fields.Float(default=1.0)
    price_unit = fields.Float()
    tax_percent = fields.Float(string="Tax %")
    amount = fields.Float()
    product_id = fields.Many2one("product.product", string="Product")
