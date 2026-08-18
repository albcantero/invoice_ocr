"""Capa 2: extracción de campos de factura española a partir de texto OCR.

Python puro, sin dependencias de Odoo. Se testea con pytest en local.
"""
import re


def parse_amount_es(token):
    """Convierte un importe en formato español a float.

    "." como separador de miles, "," como decimal. Devuelve None si no hay
    dígitos. Ejemplos: "1.234,56" -> 1234.56 ; "272,25 €" -> 272.25.
    """
    if token is None:
        return None
    s = re.sub(r"[^\d.,-]", "", str(token))
    if not re.search(r"\d", s):
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return None
