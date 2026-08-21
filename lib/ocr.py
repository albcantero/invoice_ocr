"""Capa 1: texto embebido de un PDF digital. Sin dependencias externas.

Usa pypdf / PyPDF2 (que Odoo ya trae). El OCR de imagenes/escaneados quedo
fuera de la fase alpha: si el PDF no tiene capa de texto, se avisa con claridad.
"""

import io


class NoTextLayer(Exception):
    """El PDF no tiene capa de texto (escaneo o imagen)."""


def _reader(data):
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    return PdfReader(io.BytesIO(data))


def _is_pdf(data, mimetype):
    return mimetype == "application/pdf" or (data or b"")[:5] == b"%PDF-"


def file_to_text(data, mimetype=None):
    """Texto embebido de un PDF digital. Lanza NoTextLayer si no lo tiene."""
    if not _is_pdf(data, mimetype):
        raise NoTextLayer(
            "El archivo no es un PDF digital. Esta version solo admite PDF con "
            "capa de texto (no escaneos ni imagenes)."
        )
    reader = _reader(data)
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if not text.strip():
        raise NoTextLayer(
            "Este PDF no tiene capa de texto (parece un escaneo o una foto). "
            "El OCR de imagenes esta desactivado en esta version."
        )
    return text
