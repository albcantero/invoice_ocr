# invoice_ocr — Despliegue y operaciones

Cómo se instala y opera el módulo. La base es **plug-and-play**: sin dependencias que instalar. La capa LLM (fase beta, **parkeada**) sí requiere instalación y va como apéndice opcional al final.

Entorno de referencia: Ubuntu 24.04, Odoo 19 como paquete `.deb` (usuario `odoo`, config `/etc/odoo/odoo.conf`), addons custom en `/opt/custom_addons`.

---

## 1. Dependencias

**Ninguna que instalar.** El módulo usa solo lo que Odoo ya trae:

- `pypdf` / `PyPDF2`: lectura del texto y de las posiciones de palabra del PDF.
- pdf.js (`web/static/lib/pdfjs`): render de la página en el editor de plantillas.

Sin paquetes `pip`, sin binarios de sistema (ni Tesseract, ni poppler, ni opencv).

**Límite de alcance:** solo **PDF digital** (con capa de texto). Un escaneo o foto (PDF sin texto) deja el documento en estado *error* con un aviso claro; el OCR de imágenes está desactivado en esta versión.

---

## 2. Instalación del módulo

1. Copiar el módulo a la ruta de addons (`/opt/custom_addons/invoice_ocr`), legible por el usuario `odoo`.
2. Instalarlo desde Odoo (categoría Contabilidad). Menú: **Contabilidad → Escáner de facturas**.

**Nota:** el módulo es `application` y Odoo renderiza su descripción; necesita `static/description/index.html` o falla al instalar con un error de `docutils`. Ya está incluido.

---

## 3. Operación

- **Subir facturas**: Escáner de facturas → Subir facturas (asistente multi-archivo).
- **Revisar**: cada documento queda en *Para revisar* con la cabecera extraída; botón **Crear factura** genera el borrador de `account.move`.
- **Plantillas por proveedor**: en un documento con proveedor casado, botón **Plantilla del proveedor** → editor con el PDF real (pdf.js) y capa de dibujo. Defines las zonas de cada campo y guardas. Las siguientes facturas de ese proveedor se leen de la plantilla (manda sobre la heurística). Listado en Escáner de facturas → **Plantillas**.

---

## 4. Aprendizajes (gotchas reales)

- **`static/description/index.html`** obligatorio o `docutils` peta al instalar (módulo `application`).
- El **`__init__.py` raíz protege `import odoo`** para que el `pytest` local de la capa pura no arrastre Odoo.
- Los **tests de la capa pura** van en `tests_unit/` por `sys.path`, separados del paquete `tests/` de Odoo.
- El texto embebido **pega etiqueta+valor** ("Fecha18/08/2026") → regex con *lookbehind* (no `\b`).
- **pypdf da el texto por líneas**, no por palabra: los parsers de cada campo (CIF, fecha, importes) limpian el trozo, así que la granularidad de línea basta para la cabecera. Si en facturas reales molesta, la vía es **vendorizar `pdfminer.six`** (Python puro, MIT) en `lib/` para cajas por palabra, sin romper el plug-and-play. (PyMuPDF no sirve para vendorizar: es C compilado y AGPL.)

---

## Apéndice — Fase beta LLM (PARKEADA, requiere instalación)

Esta parte **no está activa**. Solo aplica si se reactiva el enriquecimiento por LLM local (líneas de detalle). Al hacerlo, deja de ser plug-and-play.

### Dependencias

| Para | Paquetes (`pip`) | Fichero |
|---|---|---|
| LLM embebido | `llama-cpp-python`, `huggingface-hub` | `requirements-llm.txt` |

- `llama-cpp-python` en CPU con wheel precompilada (evita compilar): `pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`.

### Backend Ollama (recomendado; único camino a GPU en red)

- `curl -fsSL https://ollama.com/install.sh | sh` → servicio en `127.0.0.1:11434`.
- `ollama pull qwen2.5:1.5b` (rápido) / `:3b` (mejor calidad de líneas).
- Ajustes del módulo: backend = Ollama, URL, modelo.
- **GPU en otra máquina**: Ollama con `OLLAMA_HOST=0.0.0.0` (+ abrir el 11434) y la URL del módulo apuntando a su IP. Ollama usa la GPU sola.

### Backend embebido (`llama-cpp-python`, en proceso)

- `pip install -r requirements-llm.txt` + descargar el `.gguf` al models dir (legible por `odoo`: `chmod -R a+rX`).
- **Subir los límites de memoria por worker** de Odoo o falla con `Failed to create llama_context` (tope de espacio de direcciones del worker, aunque sobre RAM). En `/etc/odoo/odoo.conf`:
  ```ini
  limit_memory_soft = 5368709120   ; 5 GB
  limit_memory_hard = 6442450944   ; 6 GB
  ```

### Rendimiento (medido)

| Entorno | Modelo | Tiempo por factura |
|---|---|---|
| CPU (VM 4 vCPU, sin GPU) | 1.5B | ~1 min (en segundo plano) |
| GPU (NVIDIA RTX 4060 Ti, Ollama) | 1.5B | **~1,5 s en caliente** (~200 tok/s) |

Nivel "Holded" (~2 s) es alcanzable **local y sin API** con una GPU modesta. El **gate de coherencia** (suma de líneas vs base heurística) cae a **línea única** si el modelo pequeño descuadra, para no ensuciar la factura.
