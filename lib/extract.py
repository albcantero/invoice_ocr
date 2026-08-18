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


_NIF_RE = re.compile(r"\b\d{8}[A-Za-z]\b")
_CIF_RE = re.compile(r"\b[ABCDEFGHJNPQRSUVWabcdefghjnpqrsuvw]\d{7}[0-9A-Ja-j]\b")
_NIE_RE = re.compile(r"\b[XYZxyz]\d{7}[A-Za-z]\b")


def parse_spanish_vat(text):
    """Devuelve el primer CIF/NIF/NIE plausible en el texto, en mayúsculas."""
    if not text:
        return None
    for pattern in (_NIE_RE, _CIF_RE, _NIF_RE):
        match = pattern.search(text)
        if match:
            return match.group(0).upper()
    return None
