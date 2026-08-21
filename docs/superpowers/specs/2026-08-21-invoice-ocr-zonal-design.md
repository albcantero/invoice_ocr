# invoice_ocr — OCR zonal por plantillas (cabecera) + editor mínimo

- **Fecha**: 2026-08-21
- **Estado**: propuesta / en implementación (aprobado, "empieza ya")
- **Repo**: github.com/albcantero/invoice_ocr (rama `19.0`)
- **Odoo**: 19.0

## 1. Objetivo

Extracción **por plantilla zonal** para **PDFs digitales** (nunca fotos): el usuario define, una vez por proveedor, en qué zona de la página está cada campo; a partir de ahí, todas las facturas de ese proveedor se leen de forma **exacta y determinista** sin heurística ni LLM. Primera fase: **cabecera** + un **editor visual mínimo** para dibujar las zonas.

Clave técnica: en PDF digital, **PyMuPDF `page.get_text("words")` da cada palabra con su caja exacta**; no hace falta OCR, deskew ni registro. Una zona es un rectángulo; el campo son las palabras cuyo centro cae dentro.

## 2. Alcance

**En alcance:**
- **Motor zonal de cabecera** (headless): zonas rectángulo → campo, coords **normalizadas 0-1**, reutiliza los parsers de la capa 2.
- **Datos**: `invoice.ocr.template` (por proveedor) + `invoice.ocr.template.zone`.
- **Integración**: si el proveedor casado tiene plantilla activa → el motor zonal manda; si no → heurística (como ahora).
- **Editor mínimo** (client action OWL): el servidor rasteriza la página a PNG, el usuario arrastra rectángulos y etiqueta el campo, y guarda la plantilla.
- **Arranque en frío**: primera factura de un proveedor = heurística; botón para crear la plantilla desde esa factura.

**Fuera (siguiente ciclo):** líneas de detalle (zona de tabla con columnas), pulido del editor, escaneos/fotos (registro).

## 3. Arquitectura

### 3.1 Motor `lib/zonal/`
- **`engine.py` (parte pura, TDD local)**: `extract_fields(words, zones) -> dict`.
  - `words`: lista de `(x0, y0, x1, y1, text)` en coords **normalizadas 0-1**.
  - `zones`: lista de `{field_key, x0, y0, x1, y1}`.
  - Por zona: coge las palabras cuyo **centro** cae dentro, las ordena (y, luego x), une el texto, y aplica el **parser del campo** (`parse_spanish_vat`, `parse_date_es`, `parse_amount_es`, o crudo). `field_key` ∈ {`partner_vat`, `invoice_date`, `ref`, `amount_untaxed`, `amount_tax`, `amount_total`}.
- **`pdf.py` (adaptador PyMuPDF, se prueba en VM)**: `pdf_to_words(pdf_bytes, page=0) -> words normalizadas` con `page.get_text("words")` y dividiendo por el tamaño de página.

### 3.2 Datos
- **`invoice.ocr.template`**: `name`, `partner_id` (Many2one res.partner, único por proveedor activo), `active` (default True).
- **`invoice.ocr.template.zone`**: `template_id` (ondelete cascade), `field_key` (Selection con los 6 campos), `x0`, `y0`, `x1`, `y1` (Float, 0-1).

### 3.3 Integración (documento)
- En `_apply_extraction` (o tras casar el proveedor): si `partner_id` tiene una `invoice.ocr.template` activa → `pdf_to_words(adjunto)` + `extract_fields(words, template.zones)` → esos valores **sobrescriben** los de la heurística (son exactos para ese proveedor). Si no hay plantilla → heurística sola.
- La detección de plantilla depende de casar el proveedor por CIF (ya existe). Cold-start: sin plantilla, flujo actual.

### 3.4 Editor mínimo (client action OWL, patrón `hmf_dashboard`)
- Botón "Crear/editar plantilla del proveedor" en el documento → abre el editor cargando **el PNG de la página de esta factura** (server: `page.get_pixmap()` → base64) + las zonas actuales de la plantilla (si hay).
- El usuario **arrastra** un rectángulo sobre la imagen, elige el **campo** en un desplegable, repite; **Guardar** crea/actualiza `invoice.ocr.template` (+ zonas) para el proveedor, con las coords **normalizadas** a partir de los píxeles dibujados y el tamaño mostrado.
- UI sobria (es para "verlo"), sin pdf.js: el render lo hace el servidor.

## 4. Tests
- **Parte pura del motor** (`tests_unit/test_zonal.py`, pytest local): fixtures de `words` sintéticas + zonas → asserts de campos, incluida la reutilización de parsers (CIF, importe español, fecha).
- **Adaptador PyMuPDF** + **integración Odoo** (plantilla manda sobre heurística; el editor guarda zonas normalizadas): en la VM.

## 5. Global constraints
- Odoo 19, depende de `account`. **PDF digital** (nunca foto). Sin API externa.
- Coords **normalizadas 0-1**. Reutilizar parsers de `lib/extract.py` (no duplicar).
- Identificadores en inglés; español en strings/help; peninsular; no usar "—". Commits **sin** `Co-Authored-By`.
- Convive con la fase alpha (heurística); la capa LLM sigue parkeada.

## 6. Supuestos / abiertos
- Una plantilla activa por proveedor (v1). Multi-layout por proveedor = futuro.
- Página 0 por defecto (facturas de 1 página); multipágina = futuro.
