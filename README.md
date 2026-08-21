# invoice_ocr

Escáner de facturas de proveedor para **Odoo 19**, **local y sin API externa**, **sin dependencias que instalar** (plug-and-play). Réplica funcional del escáner de Holded, con revisión humana antes de contabilizar.

## Cómo funciona

Subes una factura (PDF **digital**), el módulo extrae la cabecera (proveedor por CIF/NIF, fecha, nº, base, IVA, total) y prepara un borrador de `account.move` para que lo revises y confirmes. Dos vías de extracción, combinables:

1. **Heurística** (siempre activa): lee el texto embebido del PDF y saca los campos con reglas para factura española (CIF/NIF/NIE, importes `1.234,56`, fechas, anclas BASE/IVA/TOTAL). Instantánea.
2. **Plantillas zonales** (por proveedor): defines visualmente **dónde** está cada campo en la factura de ese proveedor (dibujas rectángulos sobre el PDF). La primera factura de un proveedor la revisas a mano; guardas su plantilla y, a partir de ahí, sus facturas se leen exactas de esas zonas. **La plantilla manda sobre la heurística.**

> Solo **PDF digital** (con capa de texto). Escaneos y fotos quedan fuera de esta versión: si el PDF no tiene texto, el documento queda en error avisándolo.

## Sin dependencias (plug-and-play)

No hay que instalar nada en el Python de Odoo ni binarios de sistema. El módulo usa solo lo que Odoo ya trae:

- **`pypdf` / `PyPDF2`**: leer el texto y las posiciones de las palabras del PDF.
- **pdf.js** (el visor de PDF de Odoo): renderizar la página en el editor de plantillas.

Copia el módulo a la ruta de addons e instálalo desde Odoo (categoría Contabilidad). Menú: **Contabilidad → Escáner de facturas** (documentos y **Plantillas**).

## Editor de plantillas

En un documento con proveedor casado, botón **"Plantilla del proveedor"**: se abre un editor que muestra el **PDF real** (pdf.js) con una capa transparente encima. Eliges un campo, dibujas su rectángulo (con una × para borrarlo), y guardas. Cada zona se guarda en coordenadas normalizadas (0-1), así que vale para cualquier tamaño de página.

## Fase beta: enriquecimiento por LLM local (PARKEADA)

Existe una capa opcional que, con un **LLM local** (sin API), extrae además las **líneas de detalle** y el vencimiento. Está **implementada pero desconectada**: el código sigue intacto en `lib/llm/` y en los métodos `_apply_llm_result` / `_cron_llm_enrichment` / `_get_llm_backend`.

Reactivarla: descomentar en `__manifest__.py` las líneas `data/ir_cron.xml` y `views/res_config_settings_views.xml`; en `models/__init__.py` el `from . import res_config_settings`; en `action_process` el bloque `llm_enabled`; y en `views/invoice_ocr_document_views.xml` las secciones LLM. Instrucciones, backends (Ollama / embebido) y rendimiento (GPU) en `docs/DEPLOYMENT.md`.

Sin API externa: los datos no salen del servidor.
