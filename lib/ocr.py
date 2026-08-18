"""Capa 1: OCR de archivo (PDF o imagen) a texto. rapidocr + PyMuPDF.

Sin dependencias de Odoo. Las importaciones pesadas son perezosas para que
importar este módulo no exija rapidocr salvo cuando se usa de verdad.
"""

_engine = None


def _get_engine():
    """Devuelve el motor rapidocr, instanciado una sola vez (queda caliente)."""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def _to_images(data, mimetype):
    """Devuelve una lista de imágenes PNG (bytes). Los PDF se rasterizan."""
    is_pdf = mimetype == "application/pdf" or data[:5] == b"%PDF-"
    if is_pdf:
        import fitz

        images = []
        with fitz.open(stream=data, filetype="pdf") as document:
            for page in document:
                pixmap = page.get_pixmap(dpi=250)
                images.append(pixmap.tobytes("png"))
        return images
    return [data]


def file_to_text(data, mimetype=None):
    """OCR de un archivo (bytes) a texto plano."""
    engine = _get_engine()
    texts = []
    for image in _to_images(data, mimetype):
        result, _elapsed = engine(image)
        if result:
            texts.append("\n".join(line[1] for line in result))
    return "\n".join(texts)
