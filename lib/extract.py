"""Capa 2: extracción de campos de factura española a partir de texto OCR.

Python puro, sin dependencias de Odoo. Se testea con pytest en local.
"""
import datetime
import re
from dataclasses import dataclass


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


_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})(?!\d)")
_REF_CODE_RE = re.compile(r"\b([A-Za-z]{1,5}[/-]\d{2,4}[/-]\d{2,6})\b")
_REF_FALLBACK_RE = re.compile(
    r"FACTURA\s*(?:N[º°o.]{0,2}|[:#])?\s*([A-Za-z0-9\-/.]*\d[A-Za-z0-9\-/.]*)",
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
    """Número de factura. Prioriza un código tipo INV/2026/00048 o F-2026/45
    cercano a la palabra 'factura'; si no, un token con dígito tras 'FACTURA'."""
    if not text:
        return None
    matches = list(_REF_CODE_RE.finditer(text))
    if matches:
        anchor = text.lower().find("factura")
        if anchor != -1:
            matches.sort(key=lambda m: abs(m.start() - anchor))
        return matches[0].group(1)
    match = _REF_FALLBACK_RE.search(text)
    if match:
        return match.group(1).strip(" .")
    return None


# Importe español con 2 decimales obligatorios: evita capturar "21%" como cifra.
_MONEY_RE = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2}")


def find_amounts(text):
    """Localiza base/IVA/total por sus anclas. El importe puede estar en la
    misma línea del ancla o en una de las siguientes (layouts en columna)."""
    result = {"base": None, "iva": None, "total": None}
    lines = (text or "").splitlines()

    def money_near(index):
        for offset, line in enumerate(lines[index : index + 3]):
            monies = _MONEY_RE.findall(line)
            if monies:
                return parse_amount_es(monies[-1] if offset == 0 else monies[0])
        return None

    for index, line in enumerate(lines):
        upper = line.upper()
        if result["total"] is None and "TOTAL" in upper:
            result["total"] = money_near(index)
        elif result["base"] is None and "BASE" in upper:
            result["base"] = money_near(index)
        elif result["iva"] is None and ("IVA" in upper or "I.V.A" in upper):
            result["iva"] = money_near(index)
    return result


@dataclass
class ExtractedInvoice:
    partner_vat: "str | None" = None
    invoice_date: "datetime.date | None" = None
    ref: "str | None" = None
    amount_untaxed: "float | None" = None
    amount_tax: "float | None" = None
    amount_total: "float | None" = None
    amounts_consistent: bool = False


def extract_invoice_fields(text):
    """Orquesta la extracción de la cabecera de una factura española."""
    text = text or ""
    amounts = find_amounts(text)
    base, iva, total = amounts["base"], amounts["iva"], amounts["total"]
    consistent = (
        base is not None
        and iva is not None
        and total is not None
        and abs((base + iva) - total) <= 0.02
    )
    return ExtractedInvoice(
        partner_vat=parse_spanish_vat(text),
        invoice_date=parse_date_es(text),
        ref=parse_ref(text),
        amount_untaxed=base,
        amount_tax=iva,
        amount_total=total,
        amounts_consistent=consistent,
    )
