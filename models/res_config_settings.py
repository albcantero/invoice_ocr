from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    invoice_ocr_llm_enabled = fields.Boolean(
        string="Enable LLM enrichment",
        config_parameter="invoice_ocr.llm_enabled",
    )
    invoice_ocr_llm_backend = fields.Selection(
        [("embedded", "Embedded (llama.cpp)"), ("ollama", "Ollama (localhost)")],
        string="LLM backend", default="embedded",
        config_parameter="invoice_ocr.llm_backend",
    )
    invoice_ocr_llm_model = fields.Selection(
        [("fast", "Rápido (1.5B)"), ("quality", "Mejor (3B)")],
        string="LLM model", default="fast",
        config_parameter="invoice_ocr.llm_model",
    )
    invoice_ocr_llm_models_dir = fields.Char(
        string="Models directory (.gguf)",
        config_parameter="invoice_ocr.llm_models_dir",
    )
    invoice_ocr_llm_ollama_url = fields.Char(
        string="Ollama URL", default="http://127.0.0.1:11434",
        config_parameter="invoice_ocr.llm_ollama_url",
    )

    def set_values(self):
        res = super().set_values()
        cron = self.env.ref("invoice_ocr.ir_cron_invoice_ocr_llm", raise_if_not_found=False)
        if cron:
            cron.active = bool(self.invoice_ocr_llm_enabled)
        return res
