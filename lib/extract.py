"""Capa 2: extracción de campos de factura española a partir de texto OCR.

Python puro, sin dependencias de Odoo. Se testea con pytest en local.
"""
import datetime
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


_DATE_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
_REF_RE = re.compile(
    r"FACTURA\s*(?:N[º°o.]{0,2})?\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/.]{2,})",
    re.IGNORECASE,
)


def parse_date_es(text):
    """Devuelve la primera fecha válida; prefiere la más cercana a 'FECHA'."""
    if not text:
        return None
    candidates = []
    for match in _DATE_RE.finditer(text):
        day, month, year = (int(match.group(i)) for i in (1, 2, 3))
        if year < 100:
            year += 2000
        try:
            candidates.append((match.start(), datetime.date(year, month, day)))
        except ValueError:
            continue
    if not candidates:
        return None
    anchor = text.lower().find("fecha")
    if anchor != -1:
        candidates.sort(key=lambda c: abs(c[0] - anchor))
    return candidates[0][1]


def parse_ref(text):
    """Devuelve el número de factura tras el ancla 'FACTURA'."""
    if not text:
        return None
    match = _REF_RE.search(text)
    if match:
        return match.group(1).strip(" .")
    return None
