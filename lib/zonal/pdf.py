"""Adaptador PyMuPDF: PDF digital -> palabras con caja normalizada 0-1.

Importa fitz de forma perezosa (solo se usa al procesar un PDF)."""


def pdf_to_words(data, page=0):
    """Devuelve [(x0, y0, x1, y1, texto)] en coordenadas normalizadas 0-1."""
    import fitz

    with fitz.open(stream=data, filetype="pdf") as document:
        pg = document[page]
        width = pg.rect.width or 1.0
        height = pg.rect.height or 1.0
        words = []
        for x0, y0, x1, y1, text, *_rest in pg.get_text("words"):
            words.append((x0 / width, y0 / height, x1 / width, y1 / height, text))
    return words
