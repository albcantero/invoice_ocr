# invoice_ocr — Diseño (MVP)

- **Fecha**: 2026-08-18
- **Estado**: propuesta, pendiente de revisión
- **Repo**: github.com/albcantero/invoice_ocr (rama `19.0`)
- **Odoo**: 19.0

## 1. Objetivo

Módulo Odoo reutilizable que digitaliza **facturas de proveedor** con OCR local (sin API externa, sin Node), extrae la cabecera y crea un borrador de `account.move`. Es la réplica funcional del "Escáner" de Holded, con el paso de revisión humana como red de seguridad: el módulo prerellena, la persona confirma.

## 2. Alcance

**MVP (esta fase):**
- Solo **facturas de proveedor**.
- Subida manual de archivos desde el cliente de Odoo (PDF, JPG, PNG, WEBP, BMP).
- Extracción de **cabecera**: proveedor (casado por CIF/NIF contra `res.partner`), fecha, nº de factura, base imponible, IVA, total.
- Confirmar → borrador de `account.move` (`in_invoice`) con una línea = total.
- UI: vistas Odoo estándar ("cerebro primero").

**Fuera de alcance (fases futuras), decidido:**
- Albaranes de proveedor → fase 2.
- Líneas de detalle → fase 2.
- Plantillas por proveedor por coordenadas → mejora futura de la capa 2.
- Buzón por email tipo holdedbox → fase futura.
- Pantalla "Escáner" OWL estilo Modernist → fase siguiente al MVP.

**No-goals (requisitos duros):**
- Nada de API de pago por uso.
- Nada de Node / Chromium / Transformers.js.
- Nada de GPU obligatoria (todo CPU, ONNX).

## 3. Arquitectura: dos capas + Odoo

```
archivo (PDF/imagen)
      │
      ▼
[Capa 1: OCR]  rapidocr-onnxruntime + PyMuPDF
      │        archivo → texto + cajas (coordenadas)
      ▼
[Capa 2: extracción]  heurística factura española (Python puro, sin ML)
      │        texto → {partner_vat, invoice_date, ref, base, iva, total}
      ▼
[Odoo: invoice.ocr.document]  registro Inbox con estado + campos
      │        revisión humana
      ▼
account.move (borrador in_invoice)
```

- **Capa 1 y 2 son helpers Python desacoplados de Odoo** (funciones/clases sin ORM). Así la capa 2 se testea con `pytest` sin Odoo, y la capa 1 se prueba con imágenes de muestra.
- **Odoo** solo orquesta: guarda el archivo, llama a las capas, persiste el resultado en `invoice.ocr.document` y ofrece la revisión + creación de la factura.

## 4. Modelo de datos: `invoice.ocr.document`

El registro Inbox. Nombre de modelo estable pese a que el módulo sea "invoice": en fase 2 el albarán se añade con un valor de `document_type`, sin renombrar el modelo (evitamos migraciones dolorosas, ver feedback de migraciones Odoo).

| Campo | Tipo | Notas |
|---|---|---|
| `name` | Char | Nombre del fichero subido |
| `attachment_id` | Many2one `ir.attachment` | El archivo original (PDF/imagen) |
| `document_type` | Selection | `invoice` (único en MVP); `delivery` en fase 2 |
| `state` | Selection | `new` → `processing` → `to_review` → `done`; más `error` |
| `partner_id` | Many2one `res.partner` | Proveedor casado (por VAT) |
| `partner_vat` | Char | CIF/NIF leído en crudo (para depurar y casar) |
| `invoice_date` | Date | Fecha de factura detectada |
| `ref` | Char | Nº de factura del proveedor |
| `amount_untaxed` | Monetary | Base imponible |
| `amount_tax` | Monetary | Cuota de IVA |
| `amount_total` | Monetary | Total |
| `currency_id` | Many2one | Moneda (por defecto la de la compañía) |
| `raw_text` | Text | Todo el texto OCR, para depurar |
| `move_id` | Many2one `account.move` | La factura creada al confirmar |
| `error_message` | Text | Motivo si `state = error` |

**Máquina de estados:**
- `new`: archivo subido, aún sin procesar.
- `processing`: OCR + extracción en curso.
- `to_review`: procesado; hay datos (aunque falten campos) listos para revisión.
- `error`: el OCR falló (archivo corrupto, sin texto legible...). `error_message` explica.
- `done`: factura creada; `move_id` apunta al borrador.

Los contadores de la UI (Nuevos / A revisar / Errores de Holded) se derivan de `state`.

## 5. Capa 1: pipeline OCR

Helper `invoice_ocr/lib/ocr.py` (o similar), sin dependencias de Odoo.

1. **Entrada**: bytes del archivo + mimetype.
2. **PDF** → `PyMuPDF` (`fitz`) rasteriza cada página a PNG (~200-300 DPI). **Imagen** → se usa directa.
3. **rapidocr** procesa cada imagen → lista de `(caja, texto, score)`.
4. Se ordena espacialmente (por fila/columna aproximada) → `raw_text`, conservando las cajas por si la capa 2 las necesita.

**Detalles de despliegue:**
- **Modelo caliente**: rapidocr se instancia **una vez** (singleton perezoso por worker) y se reutiliza entre peticiones. No se recarga por documento.
- **Modelos offline**: `rapidocr-onnxruntime` trae los modelos ONNX dentro del paquete; **no descarga nada de internet** en runtime (ventaja frente a Transformers.js, y bien para clientes sin salida a internet).
- **Idioma**: configurar el modelo de reconocimiento **latino** (p. ej. `latin_PP-OCRv3_rec`) en vez del chino/inglés por defecto, para tildes y ñ. Fallback al modelo por defecto si complica; los importes y CIF (dígitos + latín básico) salen bien igualmente.

## 6. Capa 2: extracción de factura española

Helper `invoice_ocr/lib/extract.py`, **funciones puras** `texto → campos`. Es el trabajo de verdad y donde se juega el acierto. Todo con TDD.

- **`partner_vat`**: regex de CIF/NIF español (letra+8díg, 8díg+letra, formas con guion...). Se normaliza y se casa contra `res.partner.vat` (comparación tolerante a puntos/espacios). Si casa → `partner_id`.
- **Importes**: se localizan por anclas: "BASE"/"BASE IMPONIBLE", "IVA"/"I.V.A."/"IVA 21%", "TOTAL". Parseo en **formato español** (`1.234,56` → `1234.56`). Coherencia: si `base + iva ≈ total`, sube la confianza.
- **`invoice_date`**: regex de fecha (`dd/mm/aaaa`, `dd-mm-aa`, etc.), preferencia cerca de "FECHA". Se normaliza a `Date`.
- **`ref`**: cerca de "Nº FACTURA"/"FACTURA Nº"/"FACTURA"/"Nº".
- **Gancho de plantilla por proveedor** (interfaz preparada, sin implementar en MVP): una vez casado el proveedor, permitir reglas específicas por coordenadas que sobrescriban la heurística genérica. Fase futura.

La capa 2 devuelve un dict con los campos + señales de confianza; nunca lanza por un campo que falte, solo lo deja vacío para que la revisión lo complete.

## 7. Confirmar → `account.move`

Botón "Crear factura" en el registro `to_review`:
- Crea `account.move` con `move_type = 'in_invoice'`, `partner_id`, `invoice_date`, `ref`.
- **Una línea**: `price_unit = amount_untaxed` (base) e intenta adjuntar el `account.tax` de compra cuyo porcentaje case con `amount_tax/amount_untaxed`. **Por defecto 21%** (IVA general). Si no se puede mapear con confianza, cae a `price_unit = amount_total` sin impuesto.
- Cuenta contable: se deja la de por defecto (diario/proveedor); el usuario ajusta en el borrador.
- El `move` se crea **en borrador** (nunca se contabiliza solo). Se pasa `state = done`, se enlaza `move_id` y se abre la factura.

Simplificación MVP asumida: la línea es un resumen (base + IVA), no el detalle. El borrador queda listo para que la persona lo revise y contabilice.

## 8. UI (MVP, "cerebro primero")

Vistas Odoo estándar, sin OWL todavía:
- **Acción de subida**: asistente/acción que acepta múltiples ficheros; crea un `invoice.ocr.document` por archivo y dispara el procesado.
- **Vista lista**: con `decoration-*` por `state` (badges Nuevos/A revisar/Errores), columnas proveedor, fecha, nº, total, estado.
- **Vista formulario**: previsualización del adjunto + campos extraídos editables + botón "Crear factura". Aquí se revisa y corrige antes de crear.
- **Menú**: `menuitem` nuevo dentro de **Contabilidad** (`account`), "Escáner de facturas".

La pantalla "Escáner" estilo Holded/Modernist (contadores, DataGrid, zona de arrastre) se monta **después** del MVP, reusando patrones de `hmf_dashboard` y del buscador de lista.

## 9. Procesamiento: cuándo corre el OCR

- **MVP**: al subir, cada documento se procesa de forma **síncrona** justo después (modelo caliente → pocos segundos por documento). Simple y sin dependencias extra.
- **Si hace falta no bloquear / lotes grandes**: se añade un `ir.cron` que recoge los `state = new` y los procesa en segundo plano. **Sin dependencias extra** (nada de `queue_job`). Se deja la puerta abierta en el diseño; no se implementa en MVP salvo que la subida múltiple lo pida.

## 10. Errores y estados

- OCR falla (archivo ilegible/corrupto) → `error` + `error_message`.
- Falta el total o baja coherencia base+iva/total → se queda en `to_review` con lo que haya; la persona lo completa.
- Reproceso: botón "Reintentar" que vuelve a `new`/`processing`.

## 11. Empaquetado y dependencias

- `__manifest__.py` declara `external_dependencies: {'python': ['rapidocr_onnxruntime', 'fitz']}`. Si faltan, Odoo se niega a instalar y dice cuál.
- `requirements.txt` en la raíz del módulo.
- `install.ps1` (Windows, prod) e `install.sh` (Linux) que hacen `pip install -r requirements.txt` **apuntando al Python con el que corre Odoo** (el punto fino). Los scripts detectan/piden ese intérprete.
- Sin binarios de sistema (ni Tesseract ni poppler). Solo wheels.

## 12. Tests (TDD)

- **Capa 2 (prioritaria, TDD estricto)**: `pytest` local sin Odoo. Casos con textos reales de facturas de muestra: CIF/NIF en sus variantes, importes en formato español, fechas, nº de factura, coherencia base+iva=total. Se escriben **antes** que la implementación.
- **Capa 1**: pruebas con un par de imágenes/PDF de muestra (en la VM, con las deps instaladas): que el texto esperado aparezca en `raw_text`.
- **Integración Odoo**: test de que confirmar un `invoice.ocr.document` crea el `account.move` correcto en borrador.

## 13. Flujo de trabajo / logística

- **Edición**: copia local en `C:\Users\Alberto\Desktop\invoice_ocr` (herramientas limpias + `pytest` de la capa 2 en local).
- **Repo**: `github.com/albcantero/invoice_ocr`, rama `19.0` (convención por serie, como `mail_client`).
- **Pruebas OCR/Odoo**: deploy a la VM dev (`ssh alberto@192.168.1.10`) contra el Odoo de pruebas; sync por git o scp.
- **Construcción**: guiada (Claude implementa, Alberto decide en cada paso).

## 14. Supuestos y preguntas abiertas

- Se asume que los proveedores frecuentes tienen NIF en `res.partner`; si no casa por VAT, el proveedor queda vacío para elegir en la revisión.
- Se asume factura española (formato de número e IVA). Multi-idioma/otros formatos, fuera de MVP.
- **Resuelto**: el menú es un `menuitem` nuevo dentro de Contabilidad (`account`).
- **Resuelto**: impuesto de compra por defecto para el mapeo de la línea = 21% (IVA general).
