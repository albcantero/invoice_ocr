from odoo import fields, models


class InvoiceOcrUpload(models.TransientModel):
    _name = "invoice.ocr.upload"
    _description = "Invoice OCR Upload"

    file_ids = fields.Many2many("ir.attachment", string="Files")

    def action_upload(self):
        documents = self.env["invoice.ocr.document"]
        created = documents
        for attachment in self.file_ids:
            attachment.res_model = "invoice.ocr.document"
            document = documents.create(
                {"name": attachment.name, "attachment_id": attachment.id}
            )
            attachment.res_id = document.id
            created |= document
        created.action_process()
        return {
            "type": "ir.actions.act_window",
            "res_model": "invoice.ocr.document",
            "view_mode": "list,form",
            "domain": [("id", "in", created.ids)],
        }
