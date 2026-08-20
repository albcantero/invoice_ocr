# invoice_ocr

Escáner de facturas de proveedor para **Odoo 19** con **OCR local, sin API externa**. Réplica funcional del escáner de Holded, con revisión humana antes de contabilizar.

> **Estado: fase ALPHA (solo heurística).** La capa de enriquecimiento por **LLM local (fase beta)** está implementada pero **parkeada** (código intacto en `lib/llm/` y en los métodos `_apply_llm_result` / `_cron_llm_enrichment` / `_get_llm_backend`; solo está **desconectada**). Para **reactivarla**: descomentar en `__manifest__.py` las líneas `data/ir_cron.xml` y `views/res_config_settings_views.xml`; en `models/__init__.py` el `from . import res_config_settings`; en `action_process` el bloque `llm_enabled`; y en `views/invoice_ocr_document_views.xml` las secciones LLM. Detalles del LLM en `docs/DEPLOYMENT.md` (§3-§5).

- **Fase 1**: subes una factura (PDF/imagen); la heurística extrae la cabecera (proveedor por CIF/NIF, fecha, nº, base, IVA, total) al instante y prepara un borrador de `account.move`.
- **Fase 2**: un **LLM local** en segundo plano extrae además las **líneas de detalle** (descripción, cantidad, precio, IVA por línea) y el vencimiento. Reconciliación: la heurística manda en lo determinista (CIF, importes, fechas); el LLM aporta líneas, proveedor y vencimiento, y rellena huecos.

## Instalación

1. Dependencias base, en el **Python con el que corre Odoo**: `install.sh` / `install.ps1` (instalan `requirements.txt`: `rapidocr-onnxruntime`, `PyMuPDF`). Sin binarios de sistema.
2. Copia el módulo a la ruta de addons e instálalo desde Odoo (categoría Contabilidad).

## LLM (fase 2 — líneas de detalle)

El enriquecimiento de líneas usa un LLM **local**, con backend enchufable en **Ajustes → Invoice OCR (LLM)**. Modelo seleccionable: Rápido (1.5B) / Mejor (3B).

### Backend Ollama (el más simple para empezar)
- Instala [Ollama](https://ollama.com) y `ollama pull qwen2.5:1.5b` (o `:3b`).
- Ajustes: backend = **Ollama**, URL `http://127.0.0.1:11434`.
- El modelo corre en el **proceso de Ollama** (aparte). **No requiere tocar los límites de memoria de Odoo.**

### Backend embebido (portable, `llama-cpp-python`)
- `pip install -r requirements-llm.txt` en el Python de Odoo. En CPU, usa la wheel precompilada para evitar compilar:
  `pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`.
- Descarga el `.gguf` al **models dir** configurado (p. ej. `/opt/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf`).
- **Requisitos de despliegue** (el modelo se carga **dentro del worker de Odoo**):
  - El `.gguf` (y su directorio) debe ser **legible por el usuario de Odoo**: `sudo chmod -R a+rX /opt/gguf`.
  - **Sube los límites de memoria por worker** en `odoo.conf`; si no, `llama.cpp` falla con `Failed to create llama_context` (el worker tiene un tope de espacio de direcciones que el modelo supera, aunque sobre RAM en la máquina):
    ```ini
    limit_memory_soft = 5368709120   ; 5 GB
    limit_memory_hard = 6442450944   ; 6 GB
    ```
    y reinicia Odoo.

## Rendimiento

El LLM corre en **segundo plano** (`ir.cron`, patrón cargar → procesar tanda → liberar; RAM solo al procesar). La cabecera (heurística) es **instantánea**; las líneas se rellenan después.

- **CPU** (sin GPU): ~1 min por factura con el 1.5B. Pensado para procesar **por lotes**, no para mirarlo en directo.
- **GPU / CPU potente**: segundos. El código es el mismo; la velocidad depende del hardware.
- El 3B da algo más de calidad pero es bastante más lento y pesado; en máquinas modestas, el 1.5B.

## Configuración (Ajustes → Invoice OCR (LLM))
- **Enable LLM enrichment**: activa el `ir.cron` de enriquecimiento.
- **Backend**: `embedded` (portable) / `ollama`.
- **Model**: `fast` (1.5B) / `quality` (3B).
- **Models directory**: ruta de los `.gguf` (backend embebido).
- **Ollama URL**: por defecto `http://127.0.0.1:11434`.

Sin API externa: los datos no salen del servidor.
