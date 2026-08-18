"""Molde JSON y prompt para la extracción de factura con un LLM local."""
import json

MOLD = {
    "vendor_name": None,
    "vendor_vat": None,
    "invoice_date": None,
    "invoice_ref": None,
    "due_date": None,
    "currency": None,
    "lines": [
        {"description": None, "quantity": None, "price_unit": None,
         "tax_percent": None, "amount": None}
    ],
    "amount_untaxed": None,
    "amount_tax": None,
    "amount_total": None,
}

SYSTEM_PROMPT = (
    "Eres un extractor de datos de facturas de proveedor espanolas. "
    "A partir del texto OCR, rellena EXACTAMENTE esta estructura JSON. "
    "Usa null si un dato no aparece. Importes como numeros con punto decimal "
    "(ej. 272.25). Fechas en formato YYYY-MM-DD. No inventes datos. "
    "Devuelve SOLO el JSON.\n\nEstructura:\n"
    + json.dumps(MOLD, ensure_ascii=False, indent=2)
)


def build_messages(text):
    """Mensajes chat (system + user) para el backend LLM."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "TEXTO OCR:\n" + (text or "")},
    ]
