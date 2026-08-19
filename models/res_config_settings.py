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
        [("fast", "Rapido (1.5B)"), ("quality", "Mejor (3B)")],
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
