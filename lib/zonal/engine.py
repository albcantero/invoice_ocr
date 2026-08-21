"""Motor zonal (parte pura): extrae campos de cabecera a partir de palabras
posicionadas y zonas. Sin PyMuPDF ni Odoo; se testea con pytest en local.

Reutiliza los parsers de la capa 2 (lib.extract), sin duplicar lógica.
"""
from ..extract import parse_amount_es, parse_date_es, parse_spanish_vat


def _ref_parser(text):
    text = (text or "").strip()
    return text or None


# field_key -> parser que se aplica al texto de la zona
_PARSERS = {
    "partner_vat": parse_spanish_vat,
    "invoice_date": parse_date_es,
    "ref": _ref_parser,
    "amount_untaxed": parse_amount_es,
    "amount_tax": parse_amount_es,
    "amount_total": parse_amount_es,
}


def _text_in_zone(words, x0, y0, x1, y1):
    """Une el texto de las palabras cuyo centro cae dentro de la zona,
    ordenadas por fila (y) y luego por columna (x)."""
    inside = []
    for wx0, wy0, wx1, wy1, text in words:
        cx = (wx0 + wx1) / 2.0
        cy = (wy0 + wy1) / 2.0
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            inside.append((round(cy, 4), cx, text))
    inside.sort()
    return " ".join(text for _, _, text in inside)


def extract_fields(words, zones):
    """words: lista de (x0, y0, x1, y1, texto) en coordenadas normalizadas 0-1.
    zones: lista de {field_key, x0, y0, x1, y1}. Devuelve {field_key: valor}
    aplicando el parser del campo (None si la zona no captura texto)."""
    result = {}
    for zone in zones:
        key = zone["field_key"]
        text = _text_in_zone(words, zone["x0"], zone["y0"], zone["x1"], zone["y1"])
        parser = _PARSERS.get(key, _ref_parser)
        result[key] = parser(text) if text else None
    return result
