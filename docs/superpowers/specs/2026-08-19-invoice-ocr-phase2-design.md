# invoice_ocr — Fase 2: líneas de detalle vía híbrido (heurística + LLM local)

- **Fecha**: 2026-08-19
- **Estado**: propuesta, pendiente de revisión
- **Repo**: github.com/albcantero/invoice_ocr (rama `19.0`)
- **Odoo**: 19.0
- **Base**: [[2026-08-18-invoice-ocr-design]] (MVP fase 1, ya entregado)

## 1. Objetivo

Añadir **extracción de líneas de detalle** a `invoice_ocr` mediante un **híbrido**: la heurística actual (capa 2) da la cabecera al instante; un **LLM local** construye el JSON completo (incluidas las líneas) en segundo plano. El LLM es el motor de "montar el JSON" y por tanto **núcleo de la fase 2**, no un extra.

Validado con un spike en la VM (2026-08-19): `qwen2.5:1.5b`/`:3b` local rellenan un molde JSON con **toda la factura, líneas incluidas**, en calidad muy alta. El 1.5B falla el CIF (que la heurística clava) y va 3,3× más rápido que el 3B.

## 2. Alcance

**En alcance (esta fase):**
- **Líneas de detalle**: descripción, cantidad, precio unitario, % IVA, importe.
- **LLM local** tras interfaz enchufable, backend **embebido (`llama-cpp-python`) por defecto**, Ollama como alternativa.
- **Modelo seleccionable** (1.5B rápido / 3B mejor) por configuración.
- Campos extra que da el LLM: **vencimiento** (due date) y **nombre de proveedor** (para casar cuando el CIF no casa).
- Procesado del LLM en **segundo plano** (`ir.cron`), cargar→procesar→liberar.
- Mapeo de líneas a `account.move` al confirmar.

**Fuera de alcance (ciclos futuros):**
- Albaranes de proveedor, buzón email, pantalla "Escáner" Modernist.
- Auto-categorización / aprendizaje de cuenta de gasto.
- Pedido de compra desde la factura.
- Creación automática de productos.
- Manuscrito.

**No-goals (requisitos duros):**
- El LLM corre **100% local, sin API externa** (embebido o localhost).
- El backend embebido es **portable**: sin servicio de sistema visible; RAM solo al procesar.

## 3. Arquitectura: dos tiempos + reconciliación

```
subida
  │  (síncrono, instantáneo)
  ▼
OCR (capa 1) → texto → heurística (capa 2)  → cabecera determinista + estado to_review
                                             → si llm_enabled: llm_state = pending
  │
  ▼  (asíncrono, ir.cron)
capa 3 (LLM) : texto → JSON (molde) → líneas + campos difusos
  │
  ▼
RECONCILIACIÓN → documento completo (cabecera + líneas) para revisión
```

**Regla de reconciliación** (quién gana en cada campo):

| Campo | Fuente que manda | Motivo |
|---|---|---|
| `partner_vat` (CIF) | **Heurística** | Regex infalible; el LLM pequeño lo falla |
| `amount_untaxed`/`amount_tax`/`amount_total` | **Heurística** | Anclas deterministas |
| `invoice_date`, `ref` | **Heurística** | Deterministas |
| `lines` (líneas de detalle) | **LLM** | La heurística no las saca |
| `partner_name` | **LLM** | Difuso; fallback de casado por nombre |
| `due_date` | **LLM** | La heurística no lo saca |
| Cualquier campo que la heurística deje vacío | **LLM** rellena el hueco | Complementariedad |

El LLM es **requerido** para el resultado completo. Si en un documento el LLM no puede correr (backend caído, sin modelo), ese documento queda en `error`/pendiente de reintento; no hay un "modo producto solo-cabecera".

## 4. Capa 3 (LLM): interfaz enchufable

`lib/llm/` (Python puro, sin Odoo):

- **`interface`**: `extract_invoice_json(text: str, model_id: str) -> dict` (devuelve el molde relleno como dict Python).
- **`prompt.py`**: el **molde JSON** (contrato de salida) + system prompt en español. El molde:
  ```json
  {
    "vendor_name": null, "vendor_vat": null, "invoice_date": null,
    "invoice_ref": null, "due_date": null, "currency": null,
    "lines": [{"description": null, "quantity": null, "price_unit": null,
               "tax_percent": null, "amount": null}],
    "amount_untaxed": null, "amount_tax": null, "amount_total": null
  }
  ```
- **`schema.py`**: normaliza la salida (números vía `extract.parse_amount_es`, da igual `25.0` o `"25,00"`; fechas a `date`; `%` a número) → dataclass `LlmInvoice`. **No lanza** por un campo malo; lo deja vacío.
- **`backend_embedded.py`** (por defecto): `llama-cpp-python`. Carga el `.gguf` del modelo, fuerza JSON (grammar/`response_format`), devuelve dict. Patrón **cargar → procesar tanda → liberar** (context manager).
- **`backend_ollama.py`**: POST a `http://<ollama_url>/api/chat` con `format: json` (solo `requests`, que Odoo ya trae). Misma interfaz.
- **fábrica**: elige backend (`llm_backend`) y modelo (`llm_model`) desde config.

**Selección de modelo** (`llm_model`, el desplegable estilo Perplexity):
- `fast` → 1.5B. Embebido: `qwen2.5-1.5b-instruct` `.gguf`; Ollama: `qwen2.5:1.5b`.
- `quality` → 3B. Embebido: `qwen2.5-3b-instruct` `.gguf`; Ollama: `qwen2.5:3b`.

## 5. Modelo de datos

- **Nuevo** `invoice.ocr.document.line` (One2many `line_ids` en el documento):
  - `document_id` (Many2one, ondelete cascade), `sequence`.
  - `description` (Char), `quantity` (Float), `price_unit` (Float), `tax_percent` (Float), `amount` (Float).
  - `product_id` (Many2one `product.product`, opcional: casado por nombre si existe; **nunca se crea**).
- **Campos nuevos** en `invoice.ocr.document`:
  - `line_ids` (One2many).
  - `due_date` (Date), `partner_name` (Char, crudo del LLM).
  - `llm_state` (Selection: `none`/`pending`/`processing`/`done`/`error`, default `none`).
  - `llm_error` (Text).

## 6. Líneas → `account.move` (al "Crear factura")

- Si hay `line_ids`: crear `invoice_line_ids` una por línea: `name` = descripción, `quantity`, `price_unit`, `tax_ids` = `account.tax` de compra cuyo `amount` case con `tax_percent` (por defecto 21%). `product_id` solo si se casó uno existente. **Sin crear productos.**
- Si **no** hay líneas (LLM no corrió aún o falló): cae a la **línea única con el total** del MVP.
- Coherencia: si `sum(líneas) ≈ amount_total`, se usan las líneas; si no, se marca y se cae a línea única (revisión).
- Casado de proveedor: por `partner_vat` (heurística); si no casa, intento por `partner_name` (LLM); si no, vacío para elegir en revisión.

## 7. Procesado en segundo plano

- Al subir: heurística → `to_review`; si `llm_enabled`, `llm_state = pending`.
- **`ir.cron`** "invoice_ocr: enriquecimiento LLM", cada N min:
  1. Busca `llm_state = pending` (limita el lote).
  2. Instancia el backend **una vez** (carga el modelo).
  3. Por documento: `extract_invoice_json(raw_text, model)` → normaliza → reconcilia → escribe cabecera-huecos + `line_ids`; `llm_state = done`.
  4. **Libera** el modelo al terminar la tanda.
  - Errores por documento → `llm_state = error` + `llm_error`, sin tumbar el lote.
- Sin dependencia de `queue_job`.

## 8. Configuración (`res.config.settings`)

- `llm_enabled` (Boolean).
- `llm_backend` (Selection: `embedded`/`ollama`, default `embedded`).
- `llm_model` (Selection: `fast`/`quality`, default `fast`).
- `llm_models_dir` (Char, embebido: ruta de los `.gguf`).
- `llm_ollama_url` (Char, default `http://127.0.0.1:11434`).
- Guardados como `ir.config_parameter`.

## 9. UI (vistas estándar)

- Formulario del documento: pestaña/tabla editable de `line_ids`; campos `due_date`, `partner_name`; indicador de `llm_state` ("enriqueciendo…"/"listo"/"error") con `llm_error` visible en error.
- Página de ajustes con la sección LLM (incluido el desplegable de modelo).
- La pantalla "Escáner" Modernist sigue siendo un ciclo futuro.

## 10. Empaquetado y dependencias

- **`llama-cpp-python` NO va en `external_dependencies` duro** (forzaría la librería a quien use el backend Ollama). Es **requerida para el backend embebido**: import perezoso en `backend_embedded.py` con error claro si falta, documentada en `requirements-llm.txt` e instalada por el script de setup.
- **Requisito duro de la funcionalidad**: debe haber un LLM configurado y accesible. Se valida en `res.config.settings` (aviso si `llm_enabled` sin backend operativo).
- **Modelos `.gguf` no van en git** (~1-2 GB): se descargan en el setup (script o acción de ajustes) desde HuggingFace al `llm_models_dir`.
- Hardware: el LLM pide RAM (~2-3 GB el modelo) y CPU/GPU decente; en CPU modesta va lento (por eso el procesado es en background). Documentado como requisito de despliegue.

## 11. Tests (TDD)

- **Corazón testeable en local (capa 3 pura, `pytest` sin Odoo)**:
  - `schema.normalize()`: dado el JSON crudo del modelo → `LlmInvoice` normalizado. **Fixtures = salidas reales del spike** (3B con strings `"25,00"`, 1.5B con floats `25.0`). Se escriben primero.
  - `reconcile(heuristic_result, llm_result)`: aplica la regla de la sección 3 (heurística manda en deterministas; LLM aporta líneas/difusos/huecos). Casos: LLM falla CIF → gana heurística; heurística sin líneas → gana LLM.
- **Integración Odoo (TransactionCase, VM)**: mapeo `line_ids` → `account.move` con impuestos correctos; fallback a línea única sin líneas.
- **Backend embebido/ollama**: prueba de humo en la VM con un modelo real (no en unit tests).

## 12. Supuestos y preguntas abiertas

- Se asume factura española y molde fijo; multi-idioma fuera de alcance.
- El casado de `account.tax` por porcentaje asume tipos de IVA estándar (21/10/4).
- Fuente concreta de los `.gguf` (repo HuggingFace y cuantización) a fijar en el plan.
- Cadencia del `ir.cron` (por defecto propuesta: cada 5 min; ajustable).
