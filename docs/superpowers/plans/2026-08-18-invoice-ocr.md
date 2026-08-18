# Invoice OCR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Módulo Odoo 19 que digitaliza facturas de proveedor con OCR local (sin API, sin Node), extrae la cabecera y crea un borrador de `account.move`.

**Architecture:** Dos capas de Python puro desacopladas de Odoo (capa 1 OCR con rapidocr + PyMuPDF; capa 2 extracción de factura española por heurística) más un módulo Odoo con el modelo Inbox `invoice.ocr.document`, un asistente de subida y vistas estándar. La capa 2 se desarrolla con TDD local (`pytest`, sin Odoo); las piezas Odoo se prueban en la VM.

**Tech Stack:** Odoo 19.0, Python 3, `rapidocr-onnxruntime`, `PyMuPDF` (`fitz`), `pytest` (dev).

**Spec:** `docs/superpowers/specs/2026-08-18-invoice-ocr-design.md`

## Global Constraints

- **Odoo**: 19.0. El módulo depende de `account`.
- **Sin API externa** de OCR y **sin Node/Chromium/Transformers.js**. Todo CPU, ONNX.
- **Dependencias Python** declaradas en `external_dependencies`: `rapidocr_onnxruntime`, `fitz`. Sin binarios de sistema.
- **Identificadores en inglés** (campos, métodos, modelos); español solo en `string`/`help`/labels/comentarios.
- **Español peninsular** en textos de UI; **no usar "—"** como separador (usar ":" o ";").
- **Menú**: `menuitem` nuevo dentro de Contabilidad (`account`).
- **Impuesto de compra por defecto**: 21% (IVA general).
- **Commits sin** línea `Co-Authored-By`.
- **Modelo Inbox**: `invoice.ocr.document`, estados `new` → `processing` → `to_review` → `done`, más `error`.

---

## Notas de ejecución

- **Tareas 1–6** (scaffold + capa 2): se hacen y se testean **en local** (`Desktop\invoice_ocr`) con `pytest`. Requiere `pip install pytest` en el Python local.
- **Tareas 7–12** (capa 1 + Odoo): requieren la **VM dev**. Desplegar el módulo a la ruta de addons de la VM (`ssh alberto@192.168.1.10`), instalar las dependencias con `install.sh`, y correr los tests Odoo con `odoo -c <conf> -d test_db -u invoice_ocr --test-enable --stop-after-init`.

---

## File Structure

```
invoice_ocr/
├── __init__.py                      # importa models, wizards
├── __manifest__.py
├── requirements.txt
├── install.ps1                      # Windows (prod)
├── install.sh                       # Linux (VM)
├── conftest.py                      # añade el módulo al sys.path para pytest local
├── lib/
│   ├── __init__.py                  # VACÍO (no importa Odoo ni rapidocr)
│   ├── extract.py                   # capa 2: extracción factura española (python puro)
│   └── ocr.py                       # capa 1: rapidocr + PyMuPDF
├── models/
│   ├── __init__.py
│   └── invoice_ocr_document.py      # modelo invoice.ocr.document
├── wizards/
│   ├── __init__.py
│   ├── invoice_ocr_upload.py        # asistente de subida multi-archivo
│   └── invoice_ocr_upload_views.xml
├── views/
│   ├── invoice_ocr_document_views.xml
│   └── invoice_ocr_menus.xml
├── security/
│   └── ir.model.access.csv
└── tests/
    ├── __init__.py                  # importa SOLO el test Odoo (no el de pytest)
    ├── test_extract.py              # pytest local (capa 2)
    └── test_invoice_ocr_document.py # TransactionCase (Odoo, en la VM)
```

Responsabilidades: `lib/extract.py` y `lib/ocr.py` no conocen Odoo. `models/` orquesta. `lib/__init__.py` queda vacío para que `pytest` importe `lib.extract` sin arrastrar Odoo ni rapidocr.

---

### Task 1: Scaffold del módulo y empaquetado

**Files:**
- Create: `__init__.py`, `__manifest__.py`, `requirements.txt`, `install.ps1`, `install.sh`, `conftest.py`
- Create: `lib/__init__.py` (vacío), `models/__init__.py`, `wizards/__init__.py`, `tests/__init__.py`
- Test: `pytest` colecciona sin errores

**Interfaces:**
- Produces: estructura de paquete importable; `conftest.py` pone la raíz del módulo en `sys.path`.

- [ ] **Step 1: Crear `conftest.py`** (permite `from lib.extract import ...` en pytest local)

```python
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
```

- [ ] **Step 2: Crear `lib/__init__.py` vacío**

```python
```

- [ ] **Step 3: Crear `requirements.txt`**

```
rapidocr-onnxruntime
PyMuPDF
```

- [ ] **Step 4: Crear `install.sh`**

```sh
#!/usr/bin/env sh
# Instala las dependencias Python de invoice_ocr en el Python de Odoo.
# Uso: ./install.sh [ruta/al/python-de-odoo]   (por defecto: python3)
set -e
PYTHON="${1:-python3}"
"$PYTHON" -m pip install -r "$(dirname "$0")/requirements.txt"
```

- [ ] **Step 5: Crear `install.ps1`**

```powershell
# Instala las dependencias Python de invoice_ocr en el Python de Odoo.
# Uso: .\install.ps1 -Python C:\ruta\a\python.exe
param([string]$Python = "python")
& $Python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
```

- [ ] **Step 6: Crear `__manifest__.py`**

```python
{
    'name': 'Invoice OCR',
    'version': '19.0.1.0.0',
    'summary': 'Escáner de facturas de proveedor con OCR local, sin API',
    'author': 'Alberto Cantero',
    'website': 'https://github.com/albcantero/invoice_ocr',
    'license': 'LGPL-3',
    'category': 'Accounting',
    'depends': ['account'],
    'external_dependencies': {'python': ['rapidocr_onnxruntime', 'fitz']},
    'data': [
        'security/ir.model.access.csv',
        'views/invoice_ocr_document_views.xml',
        'wizards/invoice_ocr_upload_views.xml',
        'views/invoice_ocr_menus.xml',
    ],
    'application': True,
    'installable': True,
}
```

- [ ] **Step 7: Crear los `__init__.py` de paquetes**

`__init__.py` (raíz):
```python
from . import models
from . import wizards
```

`models/__init__.py`:
```python
from . import invoice_ocr_document
```

`wizards/__init__.py`:
```python
from . import invoice_ocr_upload
```

`tests/__init__.py` (Odoo solo debe correr el test TransactionCase, no el de pytest):
```python
from . import test_invoice_ocr_document
```

- [ ] **Step 8: Verificar que el manifest es Python válido**

Run: `python -c "import ast; ast.parse(open('__manifest__.py').read()); print('ok')"`
Expected: imprime `ok`

- [ ] **Step 9: Verificar que pytest colecciona (aún 0 tests)**

Run: `pytest -q`
Expected: `no tests ran` sin errores de importación

- [ ] **Step 10: Commit**

```bash
git add __init__.py __manifest__.py requirements.txt install.ps1 install.sh conftest.py lib models wizards tests
git commit -m "feat: scaffold del modulo invoice_ocr y empaquetado"
```

---

### Task 2: Capa 2 — parseo de importes en formato español

**Files:**
- Create: `lib/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Produces: `parse_amount_es(token: str | None) -> float | None` (redondea a 2 decimales; formato español: "." miles, "," decimal).

- [ ] **Step 1: Escribir el test que falla**

```python
from lib.extract import parse_amount_es


def test_parse_amount_es_thousands_and_decimals():
    assert parse_amount_es("1.234,56") == 1234.56


def test_parse_amount_es_simple_decimal():
    assert parse_amount_es("272,25") == 272.25


def test_parse_amount_es_with_currency_symbol():
    assert parse_amount_es("272,25 €") == 272.25


def test_parse_amount_es_integer_with_thousands():
    assert parse_amount_es("1.234") == 1234.0


def test_parse_amount_es_non_numeric_returns_none():
    assert parse_amount_es("abc") is None


def test_parse_amount_es_none_returns_none():
    assert parse_amount_es(None) is None
```

- [ ] **Step 2: Correr el test para verlo fallar**

Run: `pytest tests/test_extract.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lib.extract'` (o `ImportError`)

- [ ] **Step 3: Implementación mínima en `lib/extract.py`**

```python
"""Capa 2: extracción de campos de factura española a partir de texto OCR.

Python puro, sin dependencias de Odoo. Se testea con pytest en local.
"""
import re


def parse_amount_es(token):
    """Convierte un importe en formato español a float.

    "." como separador de miles, "," como decimal. Devuelve None si no hay
    dígitos. Ejemplos: "1.234,56" -> 1234.56 ; "272,25 €" -> 272.25.
    """
    if token is None:
        return None
    s = re.sub(r"[^\d.,-]", "", str(token))
    if not re.search(r"\d", s):
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return None
```

- [ ] **Step 4: Correr el test para verlo pasar**

Run: `pytest tests/test_extract.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add lib/extract.py tests/test_extract.py
git commit -m "feat: parse_amount_es (importes en formato espanol)"
```

---

### Task 3: Capa 2 — parseo de CIF/NIF/NIE

**Files:**
- Modify: `lib/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Produces: `parse_spanish_vat(text: str | None) -> str | None` (devuelve el identificador fiscal en mayúsculas, o None).

- [ ] **Step 1: Añadir los tests que fallan**

```python
from lib.extract import parse_spanish_vat


def test_parse_vat_nif():
    assert parse_spanish_vat("Cliente 12345678Z, gracias") == "12345678Z"


def test_parse_vat_cif_with_anchor():
    assert parse_spanish_vat("CIF: B12345674") == "B12345674"


def test_parse_vat_nie():
    assert parse_spanish_vat("NIE X1234567L") == "X1234567L"


def test_parse_vat_absent_returns_none():
    assert parse_spanish_vat("sin identificador fiscal") is None
```

- [ ] **Step 2: Correr los tests nuevos para verlos fallar**

Run: `pytest tests/test_extract.py -k vat -q`
Expected: FAIL con `ImportError: cannot import name 'parse_spanish_vat'`

- [ ] **Step 3: Añadir la implementación a `lib/extract.py`**

```python
_NIF_RE = re.compile(r"\b\d{8}[A-Za-z]\b")
_CIF_RE = re.compile(r"\b[ABCDEFGHJNPQRSUVWabcdefghjnpqrsuvw]\d{7}[0-9A-Ja-j]\b")
_NIE_RE = re.compile(r"\b[XYZxyz]\d{7}[A-Za-z]\b")


def parse_spanish_vat(text):
    """Devuelve el primer CIF/NIF/NIE plausible en el texto, en mayúsculas."""
    if not text:
        return None
    for pattern in (_NIE_RE, _CIF_RE, _NIF_RE):
        match = pattern.search(text)
        if match:
            return match.group(0).upper()
    return None
```

- [ ] **Step 4: Correr los tests para verlos pasar**

Run: `pytest tests/test_extract.py -q`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add lib/extract.py tests/test_extract.py
git commit -m "feat: parse_spanish_vat (CIF/NIF/NIE)"
```

---

### Task 4: Capa 2 — parseo de fecha y número de factura

**Files:**
- Modify: `lib/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Produces: `parse_date_es(text: str | None) -> datetime.date | None` (prefiere la fecha cercana a "FECHA"); `parse_ref(text: str | None) -> str | None`.

- [ ] **Step 1: Añadir los tests que fallan**

```python
import datetime

from lib.extract import parse_date_es, parse_ref


def test_parse_date_slash_four_digit_year():
    assert parse_date_es("Fecha: 18/08/2026") == datetime.date(2026, 8, 18)


def test_parse_date_dash_two_digit_year():
    assert parse_date_es("01-02-26") == datetime.date(2026, 2, 1)


def test_parse_date_absent_returns_none():
    assert parse_date_es("sin fecha aqui") is None


def test_parse_ref_factura_number():
    assert parse_ref("FACTURA Nº F-2026/45") == "F-2026/45"


def test_parse_ref_absent_returns_none():
    assert parse_ref("documento cualquiera") is None
```

- [ ] **Step 2: Correr los tests nuevos para verlos fallar**

Run: `pytest tests/test_extract.py -k "date or ref" -q`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Añadir la implementación a `lib/extract.py`**

```python
import datetime

_DATE_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
_REF_RE = re.compile(
    r"FACTURA\s*(?:N[º°o.]{0,2})?\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/.]{2,})",
    re.IGNORECASE,
)


def parse_date_es(text):
    """Devuelve la primera fecha válida; prefiere la más cercana a 'FECHA'."""
    if not text:
        return None
    candidates = []
    for match in _DATE_RE.finditer(text):
        day, month, year = (int(match.group(i)) for i in (1, 2, 3))
        if year < 100:
            year += 2000
        try:
            candidates.append((match.start(), datetime.date(year, month, day)))
        except ValueError:
            continue
    if not candidates:
        return None
    anchor = text.lower().find("fecha")
    if anchor != -1:
        candidates.sort(key=lambda c: abs(c[0] - anchor))
    return candidates[0][1]


def parse_ref(text):
    """Devuelve el número de factura tras el ancla 'FACTURA'."""
    if not text:
        return None
    match = _REF_RE.search(text)
    if match:
        return match.group(1).strip(" .")
    return None
```

- [ ] **Step 4: Correr los tests para verlos pasar**

Run: `pytest tests/test_extract.py -q`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add lib/extract.py tests/test_extract.py
git commit -m "feat: parse_date_es y parse_ref"
```

---

### Task 5: Capa 2 — importes por anclas (base / IVA / total)

**Files:**
- Modify: `lib/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Produces: `find_amounts(text: str | None) -> dict` con claves `base`, `iva`, `total` (float o None). Ignora porcentajes (p. ej. "21%").

- [ ] **Step 1: Añadir los tests que fallan**

```python
from lib.extract import find_amounts


def test_find_amounts_base_iva_total():
    text = "BASE IMPONIBLE 225,00\nIVA 21% 47,25\nTOTAL 272,25"
    amounts = find_amounts(text)
    assert amounts["base"] == 225.00
    assert amounts["iva"] == 47.25
    assert amounts["total"] == 272.25


def test_find_amounts_ignores_percentage_on_iva_line():
    assert find_amounts("IVA 21% 47,25")["iva"] == 47.25


def test_find_amounts_missing_returns_none():
    amounts = find_amounts("Gracias por su compra")
    assert amounts == {"base": None, "iva": None, "total": None}
```

- [ ] **Step 2: Correr los tests nuevos para verlos fallar**

Run: `pytest tests/test_extract.py -k amounts -q`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Añadir la implementación a `lib/extract.py`**

```python
# Importe español con 2 decimales obligatorios: evita capturar "21%" como cifra.
_MONEY_RE = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2}")


def find_amounts(text):
    """Localiza base/IVA/total por líneas con sus anclas. El importe es el
    último token monetario de la línea (con 2 decimales), ignorando '%'."""
    result = {"base": None, "iva": None, "total": None}
    for line in (text or "").splitlines():
        upper = line.upper()
        monies = _MONEY_RE.findall(line)
        if not monies:
            continue
        amount = parse_amount_es(monies[-1])
        if "TOTAL" in upper and result["total"] is None:
            result["total"] = amount
        elif "BASE" in upper and result["base"] is None:
            result["base"] = amount
        elif ("IVA" in upper or "I.V.A" in upper) and result["iva"] is None:
            result["iva"] = amount
    return result
```

- [ ] **Step 4: Correr los tests para verlos pasar**

Run: `pytest tests/test_extract.py -q`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add lib/extract.py tests/test_extract.py
git commit -m "feat: find_amounts (base/IVA/total por anclas)"
```

---

### Task 6: Capa 2 — orquestador `extract_invoice_fields`

**Files:**
- Modify: `lib/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Produces: `ExtractedInvoice` (dataclass) y `extract_invoice_fields(text: str) -> ExtractedInvoice`. Campos: `partner_vat`, `invoice_date`, `ref`, `amount_untaxed`, `amount_tax`, `amount_total`, `amounts_consistent`.

- [ ] **Step 1: Añadir el test que falla**

```python
from lib.extract import extract_invoice_fields


def test_extract_invoice_fields_full_document():
    text = (
        "FACTURA Nº F-2026/45\n"
        "Fecha 18/08/2026\n"
        "CIF B12345674\n"
        "BASE IMPONIBLE 225,00\n"
        "IVA 21% 47,25\n"
        "TOTAL 272,25\n"
    )
    result = extract_invoice_fields(text)
    assert result.partner_vat == "B12345674"
    assert result.invoice_date == datetime.date(2026, 8, 18)
    assert result.ref == "F-2026/45"
    assert result.amount_untaxed == 225.00
    assert result.amount_tax == 47.25
    assert result.amount_total == 272.25
    assert result.amounts_consistent is True


def test_extract_invoice_fields_empty_text():
    result = extract_invoice_fields("")
    assert result.partner_vat is None
    assert result.amount_total is None
    assert result.amounts_consistent is False
```

- [ ] **Step 2: Correr el test para verlo fallar**

Run: `pytest tests/test_extract.py -k invoice_fields -q`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Añadir la implementación a `lib/extract.py`**

```python
from dataclasses import dataclass


@dataclass
class ExtractedInvoice:
    partner_vat: "str | None" = None
    invoice_date: "datetime.date | None" = None
    ref: "str | None" = None
    amount_untaxed: "float | None" = None
    amount_tax: "float | None" = None
    amount_total: "float | None" = None
    amounts_consistent: bool = False


def extract_invoice_fields(text):
    """Orquesta la extracción de la cabecera de una factura española."""
    text = text or ""
    amounts = find_amounts(text)
    base, iva, total = amounts["base"], amounts["iva"], amounts["total"]
    consistent = (
        base is not None
        and iva is not None
        and total is not None
        and abs((base + iva) - total) <= 0.02
    )
    return ExtractedInvoice(
        partner_vat=parse_spanish_vat(text),
        invoice_date=parse_date_es(text),
        ref=parse_ref(text),
        amount_untaxed=base,
        amount_tax=iva,
        amount_total=total,
        amounts_consistent=consistent,
    )
```

- [ ] **Step 4: Correr toda la suite para verla pasar**

Run: `pytest tests/test_extract.py -q`
Expected: PASS (toda la capa 2)

- [ ] **Step 5: Commit**

```bash
git add lib/extract.py tests/test_extract.py
git commit -m "feat: extract_invoice_fields (orquestador capa 2)"
```

---

### Task 7: Capa 1 — pipeline OCR (`lib/ocr.py`)

**Requiere VM** (rapidocr + PyMuPDF instalados). Desplegar el módulo y correr allí.

**Files:**
- Create: `lib/ocr.py`
- Create: `tests/samples/sample_invoice.png` (una imagen de factura de muestra con la palabra "TOTAL" legible)
- Test: `tests/test_ocr_manual.py` (pytest en la VM, no lo importa `tests/__init__.py`)

**Interfaces:**
- Consumes: nada de la capa 2.
- Produces: `file_to_text(data: bytes, mimetype: str | None) -> str`. Motor rapidocr cacheado (singleton perezoso).

- [ ] **Step 1: Escribir el test que falla (en la VM)**

```python
import os

from lib.ocr import file_to_text

SAMPLE = os.path.join(os.path.dirname(__file__), "samples", "sample_invoice.png")


def test_file_to_text_reads_sample_image():
    with open(SAMPLE, "rb") as handle:
        data = handle.read()
    text = file_to_text(data, "image/png")
    assert "TOTAL" in text.upper()
```

- [ ] **Step 2: Correr el test para verlo fallar**

Run (VM): `pytest tests/test_ocr_manual.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lib.ocr'`

- [ ] **Step 3: Implementar `lib/ocr.py`**

```python
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
```

- [ ] **Step 4: Correr el test para verlo pasar (VM)**

Run (VM): `pytest tests/test_ocr_manual.py -q`
Expected: PASS

Nota: si las tildes/ñ salen mal, configurar un modelo de reconocimiento latino en `RapidOCR(...)`; para la cabecera (dígitos + CIF) el modelo por defecto basta.

- [ ] **Step 5: Commit**

```bash
git add lib/ocr.py tests/samples/sample_invoice.png tests/test_ocr_manual.py
git commit -m "feat: capa 1 OCR (file_to_text con rapidocr + PyMuPDF)"
```

---

### Task 8: Modelo `invoice.ocr.document` + seguridad

**Requiere VM** para instalar y verificar.

**Files:**
- Create: `models/invoice_ocr_document.py`
- Create: `security/ir.model.access.csv`

**Interfaces:**
- Produces: modelo `invoice.ocr.document` con los campos del spec y los estados `new/processing/to_review/done/error`.

- [ ] **Step 1: Crear el modelo con campos y estados**

```python
from odoo import fields, models


class InvoiceOcrDocument(models.Model):
    _name = "invoice.ocr.document"
    _description = "Invoice OCR Document"
    _order = "create_date desc"

    name = fields.Char(string="File name", required=True)
    attachment_id = fields.Many2one(
        "ir.attachment", string="File", required=True, ondelete="cascade"
    )
    document_type = fields.Selection(
        [("invoice", "Vendor Bill")], string="Type", default="invoice", required=True
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("processing", "Processing"),
            ("to_review", "To Review"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        default="new",
        required=True,
        index=True,
    )
    partner_id = fields.Many2one("res.partner", string="Vendor")
    partner_vat = fields.Char(string="VAT (raw)")
    invoice_date = fields.Date(string="Invoice date")
    ref = fields.Char(string="Bill reference")
    amount_untaxed = fields.Monetary(string="Untaxed")
    amount_tax = fields.Monetary(string="Tax")
    amount_total = fields.Monetary(string="Total")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    raw_text = fields.Text(string="OCR text")
    move_id = fields.Many2one("account.move", string="Vendor bill", readonly=True)
    error_message = fields.Text(string="Error")
```

- [ ] **Step 2: Crear `security/ir.model.access.csv`**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_invoice_ocr_document,invoice.ocr.document,model_invoice_ocr_document,account.group_account_invoice,1,1,1,1
```

- [ ] **Step 3: Desplegar a la VM e instalar el módulo**

Run (VM): `odoo -c <conf> -d test_db -i invoice_ocr --stop-after-init`
Expected: instala sin error; el log muestra `Module invoice_ocr: loading`.

- [ ] **Step 4: Verificar el modelo por shell**

Run (VM): `odoo shell -c <conf> -d test_db` y `self.env['invoice.ocr.document']`
Expected: devuelve el modelo (recordset vacío), sin excepción.

- [ ] **Step 5: Commit**

```bash
git add models/invoice_ocr_document.py security/ir.model.access.csv
git commit -m "feat: modelo invoice.ocr.document y accesos"
```

---

### Task 9: TDD `_apply_extraction` (texto → campos + casar proveedor)

**Requiere VM** (TransactionCase).

**Files:**
- Modify: `models/invoice_ocr_document.py`
- Test: `tests/test_invoice_ocr_document.py`

**Interfaces:**
- Consumes: `lib.extract.extract_invoice_fields`.
- Produces: `_apply_extraction(self, text: str) -> None` (escribe campos, casa `partner_id` por VAT, pasa a `to_review`); `_match_partner(self, vat) -> res.partner`; `_normalize_vat(vat) -> str`.

- [ ] **Step 1: Escribir el test que falla**

```python
import base64

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInvoiceOcrDocument(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {"name": "Proveedor Test", "vat": "ESB12345674"}
        )

    def _new_document(self):
        attachment = self.env["ir.attachment"].create(
            {"name": "t.pdf", "raw": base64.b64decode("")}
        )
        return self.env["invoice.ocr.document"].create(
            {"name": "t.pdf", "attachment_id": attachment.id}
        )

    def test_apply_extraction_maps_fields_and_matches_partner(self):
        text = (
            "FACTURA Nº F-2026/45\nFecha 18/08/2026\nCIF B12345674\n"
            "BASE IMPONIBLE 225,00\nIVA 21% 47,25\nTOTAL 272,25\n"
        )
        doc = self._new_document()
        doc._apply_extraction(text)
        self.assertEqual(doc.state, "to_review")
        self.assertEqual(doc.ref, "F-2026/45")
        self.assertEqual(doc.amount_untaxed, 225.00)
        self.assertEqual(doc.amount_tax, 47.25)
        self.assertEqual(doc.amount_total, 272.25)
        self.assertEqual(doc.partner_id, self.partner)
```

- [ ] **Step 2: Correr el test para verlo fallar (VM)**

Run (VM): `odoo -c <conf> -d test_db -u invoice_ocr --test-enable --test-tags /invoice_ocr --stop-after-init`
Expected: FAIL con `AttributeError: '...' object has no attribute '_apply_extraction'`

- [ ] **Step 3: Implementar el método (añadir a la clase del modelo)**

```python
from ..lib import extract as extract_lib


class InvoiceOcrDocument(models.Model):
    # ... (campos ya definidos arriba)

    @staticmethod
    def _normalize_vat(vat):
        return (vat or "").replace(" ", "").replace(".", "").replace("-", "").upper()

    def _match_partner(self, vat):
        Partner = self.env["res.partner"]
        norm = self._normalize_vat(vat)
        if not norm:
            return Partner
        candidates = [norm, "ES" + norm]
        partner = Partner.search([("vat", "in", candidates)], limit=1)
        if partner:
            return partner
        return Partner.search([("vat", "=like", "%" + norm)], limit=1)

    def _apply_extraction(self, text):
        self.ensure_one()
        result = extract_lib.extract_invoice_fields(text or "")
        vals = {
            "raw_text": text,
            "partner_vat": result.partner_vat,
            "invoice_date": result.invoice_date,
            "ref": result.ref,
            "amount_untaxed": result.amount_untaxed or 0.0,
            "amount_tax": result.amount_tax or 0.0,
            "amount_total": result.amount_total or 0.0,
            "state": "to_review",
        }
        if result.partner_vat:
            partner = self._match_partner(result.partner_vat)
            if partner:
                vals["partner_id"] = partner.id
        self.write(vals)
```

- [ ] **Step 4: Correr el test para verlo pasar (VM)**

Run (VM): `odoo -c <conf> -d test_db -u invoice_ocr --test-enable --test-tags /invoice_ocr --stop-after-init`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add models/invoice_ocr_document.py tests/test_invoice_ocr_document.py
git commit -m "feat: _apply_extraction (mapea campos y casa proveedor por VAT)"
```

---

### Task 10: TDD `action_create_bill` (→ borrador de `account.move`)

**Requiere VM.**

**Files:**
- Modify: `models/invoice_ocr_document.py`
- Test: `tests/test_invoice_ocr_document.py`

**Interfaces:**
- Produces: `action_create_bill(self)` (crea `account.move` borrador `in_invoice`, enlaza `move_id`, estado `done`); helpers `_prepare_bill_vals`, `_prepare_bill_line_vals`, `_default_purchase_tax`.

- [ ] **Step 1: Añadir el test que falla**

```python
    def test_create_bill_from_reviewed_document(self):
        text = (
            "CIF B12345674\nBASE IMPONIBLE 225,00\nIVA 21% 47,25\nTOTAL 272,25\n"
        )
        doc = self._new_document()
        doc._apply_extraction(text)
        doc.action_create_bill()
        self.assertEqual(doc.state, "done")
        self.assertTrue(doc.move_id)
        self.assertEqual(doc.move_id.move_type, "in_invoice")
        self.assertEqual(doc.move_id.state, "draft")
        self.assertEqual(doc.move_id.partner_id, self.partner)
```

- [ ] **Step 2: Correr el test para verlo fallar (VM)**

Run (VM): `odoo -c <conf> -d test_db -u invoice_ocr --test-enable --test-tags /invoice_ocr --stop-after-init`
Expected: FAIL con `AttributeError: ... 'action_create_bill'`

- [ ] **Step 3: Implementar los métodos (añadir a la clase e importar `UserError` y `_`)**

En la cabecera del fichero, ampliar el import de Odoo:
```python
from odoo import _, fields, models
from odoo.exceptions import UserError
```

Métodos:
```python
    def _default_purchase_tax(self):
        return self.env["account.tax"].search(
            [
                ("type_tax_use", "=", "purchase"),
                ("amount", "=", 21.0),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )

    def _prepare_bill_line_vals(self):
        self.ensure_one()
        tax = self._default_purchase_tax()
        vals = {
            "name": self.name or _("Scanned invoice"),
            "quantity": 1.0,
            "price_unit": self.amount_untaxed or self.amount_total or 0.0,
        }
        if tax and self.amount_untaxed:
            vals["tax_ids"] = [(6, 0, tax.ids)]
        else:
            vals["price_unit"] = self.amount_total or vals["price_unit"]
        return vals

    def _prepare_bill_vals(self):
        self.ensure_one()
        return {
            "move_type": "in_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": self.invoice_date,
            "ref": self.ref,
            "invoice_line_ids": [(0, 0, self._prepare_bill_line_vals())],
        }

    def action_create_bill(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Indica un proveedor antes de crear la factura."))
        move = self.env["account.move"].create(self._prepare_bill_vals())
        self.write({"move_id": move.id, "state": "done"})
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
        }
```

- [ ] **Step 4: Correr el test para verlo pasar (VM)**

Run (VM): `odoo -c <conf> -d test_db -u invoice_ocr --test-enable --test-tags /invoice_ocr --stop-after-init`
Expected: PASS (los dos tests de integración)

- [ ] **Step 5: Commit**

```bash
git add models/invoice_ocr_document.py tests/test_invoice_ocr_document.py
git commit -m "feat: action_create_bill (borrador de account.move)"
```

---

### Task 11: Pegamento OCR (`_ocr_text` + `action_process`)

**Requiere VM.** El OCR real necesita imágenes; se verifica a mano con la muestra.

**Files:**
- Modify: `models/invoice_ocr_document.py`

**Interfaces:**
- Consumes: `lib.ocr.file_to_text`, `_apply_extraction`.
- Produces: `_ocr_text(self) -> str`; `action_process(self)` (procesa cada documento, captura errores → estado `error`).

- [ ] **Step 1: Implementar los métodos (añadir a la clase)**

```python
    def _ocr_text(self):
        self.ensure_one()
        from ..lib import ocr as ocr_lib

        return ocr_lib.file_to_text(self.attachment_id.raw, self.attachment_id.mimetype)

    def action_process(self):
        for document in self:
            try:
                document.state = "processing"
                text = document._ocr_text()
                document._apply_extraction(text)
            except Exception as error:  # noqa: BLE001 - se refleja en el registro
                document.state = "error"
                document.error_message = str(error)
        return True
```

- [ ] **Step 2: Actualizar el módulo en la VM**

Run (VM): `odoo -c <conf> -d test_db -u invoice_ocr --stop-after-init`
Expected: recarga sin error.

- [ ] **Step 3: Verificar a mano el flujo OCR con la muestra**

Run (VM, `odoo shell`):
```python
att = self.env['ir.attachment'].create({
    'name': 'sample_invoice.png',
    'raw': open('/ruta/a/tests/samples/sample_invoice.png', 'rb').read(),
})
doc = self.env['invoice.ocr.document'].create({'name': 'sample', 'attachment_id': att.id})
doc.action_process()
print(doc.state, doc.amount_total, doc.raw_text[:200])
```
Expected: `state == 'to_review'` y `raw_text` con texto de la factura.

- [ ] **Step 4: Commit**

```bash
git add models/invoice_ocr_document.py
git commit -m "feat: action_process (OCR + extraccion con captura de errores)"
```

---

### Task 12: Asistente de subida + vistas + menú

**Requiere VM** para verificar la UI.

**Files:**
- Create: `wizards/invoice_ocr_upload.py`
- Create: `wizards/invoice_ocr_upload_views.xml`
- Create: `views/invoice_ocr_document_views.xml`
- Create: `views/invoice_ocr_menus.xml`

**Interfaces:**
- Consumes: `invoice.ocr.document.action_process`.
- Produces: modelo transitorio `invoice.ocr.upload` con `action_upload`; acciones y menús.

- [ ] **Step 1: Crear el asistente `wizards/invoice_ocr_upload.py`**

```python
from odoo import fields, models


class InvoiceOcrUpload(models.TransientModel):
    _name = "invoice.ocr.upload"
    _description = "Invoice OCR Upload"

    file_ids = fields.Many2many("ir.attachment", string="Files")

    def action_upload(self):
        documents = self.env["invoice.ocr.document"]
        created = documents
        for attachment in self.file_ids:
            attachment.res_model = "invoice.ocr.document"
            document = documents.create(
                {"name": attachment.name, "attachment_id": attachment.id}
            )
            attachment.res_id = document.id
            created |= document
        created.action_process()
        return {
            "type": "ir.actions.act_window",
            "res_model": "invoice.ocr.document",
            "view_mode": "list,form",
            "domain": [("id", "in", created.ids)],
        }
```

- [ ] **Step 2: Añadir el acceso del asistente a `security/ir.model.access.csv`**

Añadir una línea:
```csv
access_invoice_ocr_upload,invoice.ocr.upload,model_invoice_ocr_upload,account.group_account_invoice,1,1,1,1
```

- [ ] **Step 3: Crear `views/invoice_ocr_document_views.xml`**

```xml
<odoo>
    <record id="invoice_ocr_document_view_list" model="ir.ui.view">
        <field name="name">invoice.ocr.document.list</field>
        <field name="model">invoice.ocr.document</field>
        <field name="arch" type="xml">
            <list decoration-muted="state == 'done'" decoration-danger="state == 'error'">
                <field name="name"/>
                <field name="partner_id"/>
                <field name="invoice_date"/>
                <field name="ref"/>
                <field name="amount_total"/>
                <field name="state" widget="badge"
                       decoration-success="state == 'done'"
                       decoration-danger="state == 'error'"
                       decoration-info="state == 'to_review'"/>
            </list>
        </field>
    </record>

    <record id="invoice_ocr_document_view_form" model="ir.ui.view">
        <field name="name">invoice.ocr.document.form</field>
        <field name="model">invoice.ocr.document</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button name="action_process" type="object" string="Reprocesar"
                            class="btn-secondary"
                            invisible="state not in ('new', 'processing', 'to_review', 'error')"/>
                    <button name="action_create_bill" type="object" string="Crear factura"
                            class="btn-primary" invisible="state != 'to_review'"/>
                    <field name="state" widget="statusbar"
                           statusbar_visible="new,processing,to_review,done"/>
                </header>
                <sheet>
                    <group>
                        <group>
                            <field name="partner_id"/>
                            <field name="partner_vat"/>
                            <field name="invoice_date"/>
                            <field name="ref"/>
                        </group>
                        <group>
                            <field name="currency_id" invisible="1"/>
                            <field name="amount_untaxed"/>
                            <field name="amount_tax"/>
                            <field name="amount_total"/>
                            <field name="move_id" readonly="1"/>
                        </group>
                    </group>
                    <field name="error_message" readonly="1" invisible="state != 'error'"/>
                    <notebook>
                        <page string="Texto OCR">
                            <field name="raw_text" readonly="1"/>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>

    <record id="invoice_ocr_document_action" model="ir.actions.act_window">
        <field name="name">Documentos escaneados</field>
        <field name="res_model">invoice.ocr.document</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

- [ ] **Step 4: Crear `wizards/invoice_ocr_upload_views.xml`**

```xml
<odoo>
    <record id="invoice_ocr_upload_view_form" model="ir.ui.view">
        <field name="name">invoice.ocr.upload.form</field>
        <field name="model">invoice.ocr.upload</field>
        <field name="arch" type="xml">
            <form string="Subir facturas">
                <group>
                    <field name="file_ids" widget="many2many_binary"/>
                </group>
                <footer>
                    <button name="action_upload" type="object" string="Escanear"
                            class="btn-primary"/>
                    <button string="Cancelar" class="btn-secondary" special="cancel"/>
                </footer>
            </form>
        </field>
    </record>

    <record id="invoice_ocr_upload_action" model="ir.actions.act_window">
        <field name="name">Subir facturas</field>
        <field name="res_model">invoice.ocr.upload</field>
        <field name="view_mode">form</field>
        <field name="target">new</field>
    </record>
</odoo>
```

- [ ] **Step 5: Crear `views/invoice_ocr_menus.xml`**

```xml
<odoo>
    <menuitem id="menu_invoice_ocr_root" name="Escáner de facturas"
              parent="account.menu_finance" sequence="90"/>
    <menuitem id="menu_invoice_ocr_upload" name="Subir facturas"
              parent="menu_invoice_ocr_root" action="invoice_ocr_upload_action"
              sequence="10"/>
    <menuitem id="menu_invoice_ocr_documents" name="Documentos"
              parent="menu_invoice_ocr_root" action="invoice_ocr_document_action"
              sequence="20"/>
</odoo>
```

- [ ] **Step 6: Actualizar el módulo en la VM y verificar la UI a mano**

Run (VM): `odoo -c <conf> -d test_db -u invoice_ocr --stop-after-init`, luego abrir Odoo: Contabilidad → Escáner de facturas → Subir facturas, subir la muestra, ver el documento en `to_review`, pulsar "Crear factura" y comprobar el borrador.
Expected: flujo completo funciona desde la interfaz.

- [ ] **Step 7: Commit**

```bash
git add wizards views security/ir.model.access.csv
git commit -m "feat: asistente de subida, vistas y menu en Contabilidad"
```

---

## Self-Review (cobertura del spec)

- Alcance MVP (facturas, subida manual, cabecera → borrador): Tareas 8–12. ✔
- Capa 1 OCR (rapidocr + PyMuPDF, motor caliente, offline): Task 7. ✔
- Capa 2 extracción (CIF, importes es, fechas, nº, anclas): Tareas 2–6. ✔
- Modelo Inbox + estados: Task 8. ✔
- Confirmar → account.move con línea total + IVA 21%: Task 10. ✔
- Empaquetado (`external_dependencies`, `requirements.txt`, `install.*`): Task 1. ✔
- Menú en `account`: Task 12. ✔
- Tests TDD capa 2 en local; integración en VM: Tareas 2–6, 9, 10. ✔
- Tipos/nombres consistentes entre tareas (`extract_invoice_fields`, `ExtractedInvoice`, `_apply_extraction`, `action_create_bill`, `action_process`): revisado. ✔

Fuera de alcance por diseño (no son huecos): albaranes, líneas de detalle, plantillas por proveedor, `ir.cron` de proceso en segundo plano, pantalla Escáner OWL, buzón email.
