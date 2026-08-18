"""Capa 1: texto de un archivo (PDF o imagen). rapidocr + PyMuPDF.

Sin dependencias de Odoo. Las importaciones pesadas son perezosas para que
importar este módulo no exija rapidocr salvo cuando se usa de verdad.

Para PDFs digitales (con capa de texto) se lee el texto embebido directamente:
es rápido, exacto y evita el OCR (y su consumo de memoria). Solo se hace OCR
cuando no hay texto (PDF escaneado o imagen).
"""

_engine = None


def _get_engine():
    """Devuelve el motor rapidocr, instanciado una sola vez (queda caliente)."""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def _is_pdf(data, mimetype):
    return mimetype == "application/pdf" or data[:5] == b"%PDF-"


def _pdf_text_layer(data):
    """Texto embebido del PDF (vacío si es escaneado/sin capa de texto)."""
    import fitz

    parts = []
    with fitz.open(stream=data, filetype="pdf") as document:
        for page in document:
            parts.append(page.get_text())
    return "\n".join(parts)


def _to_images(data, mimetype):
    """Devuelve una lista de imágenes PNG (bytes). Los PDF se rasterizan."""
    if _is_pdf(data, mimetype):
        import fitz

        images = []
        with fitz.open(stream=data, filetype="pdf") as document:
            for page in document:
                pixmap = page.get_pixmap(dpi=150)
                images.append(pixmap.tobytes("png"))
        return images
    return [data]


def file_to_text(data, mimetype=None):
    """Texto de un archivo. Para PDF digitales usa la capa de texto embebida;
    si no hay texto (escaneado o imagen), hace OCR con rapidocr."""
    if _is_pdf(data, mimetype):
        embedded = _pdf_text_layer(data)
        if embedded and embedded.strip():
            return embedded
    engine = _get_engine()
    texts = []
    for image in _to_images(data, mimetype):
        result, _elapsed = engine(image)
        if result:
            texts.append("\n".join(line[1] for line in result))
    return "\n".join(texts)
