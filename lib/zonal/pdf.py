"""Adaptador 0-dependencias: PDF digital -> palabras con caja normalizada 0-1.

Usa pypdf / PyPDF2 (que Odoo ya trae), sin librerias externas ni compiladas.
pypdf entrega el texto por fragmentos (a menudo por linea) con su posicion de
inicio; estimamos el ancho por numero de caracteres y tamano de fuente. El motor
zonal usa el centro del fragmento y los parsers de cada campo limpian el resto,
asi que esta granularidad basta para los campos de cabecera.
"""

import io


def _reader(data):
    """PdfReader tolerante al nombre del paquete (pypdf o su predecesor PyPDF2)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    return PdfReader(io.BytesIO(data))


def pdf_to_words(data, page=0):
    """Devuelve [(x0, y0, x1, y1, texto)] en coordenadas normalizadas 0-1
    (origen arriba-izquierda, como pdf.js y como el editor)."""
    reader = _reader(data)
    pg = reader.pages[page]
    width = float(pg.mediabox.width) or 1.0
    height = float(pg.mediabox.height) or 1.0
    words = []

    def visit(text, cm, tm, font_dict, font_size):
        stripped = (text or "").strip()
        if not stripped:
            return
        # pypdf usa origen abajo-izquierda; tm[4], tm[5] es la posicion de inicio.
        x = tm[4]
        y = tm[5]
        size = font_size or 10.0
        est_width = len(stripped) * size * 0.5
        words.append((
            x / width,
            (height - y - size) / height,
            (x + est_width) / width,
            (height - y) / height,
            stripped,
        ))

    pg.extract_text(visitor_text=visit)
    return words
