# Invoice OCR Fase 2 (líneas de detalle vía híbrido) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir extracción de líneas de detalle a `invoice_ocr` con un híbrido: heurística instantánea para la cabecera + LLM local (en background) que monta el JSON completo con líneas, reconciliados.

**Architecture:** Nueva capa 3 en `lib/llm/` (Python puro: molde/prompt, normalización de la salida del modelo, reconciliación heurística+LLM, y backends enchufables embebido/ollama tras interfaz). El LLM corre en un `ir.cron` (cargar→procesar→liberar). El resultado se mapea a `account.move` al confirmar.

**Tech Stack:** Odoo 19.0, Python 3, `llama-cpp-python` (backend embebido, por defecto) u Ollama localhost (alternativo), `pytest` (dev). Reutiliza `lib/extract.py` (capa 2) y `lib/ocr.py` (capa 1).

**Spec:** `docs/superpowers/specs/2026-08-19-invoice-ocr-phase2-design.md`

## Global Constraints

- **Odoo 19.0**, el módulo depende de `account`.
- **LLM 100% local, sin API externa**: embebido (`llama-cpp-python`, por defecto) o Ollama en `localhost`.
- **Backend embebido portable**: sin servicio de sistema; RAM solo al procesar (cargar→procesar→liberar).
- **`llama_cpp` NO va en `external_dependencies` duro**: requerida solo para el backend embebido (import perezoso + error claro + `requirements-llm.txt` + setup).
- **Modelos `.gguf` NO van en git**; se descargan en el setup.
- **Reconciliación**: la heurística manda en lo determinista (`partner_vat`, importes, `invoice_date`, `ref`); el LLM aporta `lines`, `vendor_name`, `due_date` y rellena huecos.
- **No crear productos** automáticamente.
- **Modelo seleccionable**: `llm_model` = `fast` (1.5B) / `quality` (3B).
- **Background** con `ir.cron` (sin `queue_job`).
- **Identificadores en inglés**; español en strings/help; **peninsular**; no usar "—".
- **Commits sin** `Co-Authored-By`.

---

## Notas de ejecución

- **Tareas 1-4** (harness + capa 3 pura: prompt, schema, reconcile): en **local** con `pytest`.
- **Tareas 5-13** (backends + Odoo + cron): en la **VM** (`ssh alberto@192.168.1.10`). Desplegar con `tar` a `/opt/custom_addons/invoice_ocr`, parar `odoo.service` para instalar/tests, rearrancar. El backend Ollama ya está en la VM (`qwen2.5:1.5b`, `:3b`).

## File Structure

```
lib/llm/
├── __init__.py            # vacío
├── prompt.py              # MOLD + SYSTEM_PROMPT + build_messages(text)
├── schema.py              # LlmLine, LlmInvoice, normalize(raw) -> LlmInvoice
├── reconcile.py           # MergedInvoice, reconcile(heur, llm) -> MergedInvoice
├── backend_ollama.py      # OllamaBackend
├── backend_embedded.py    # EmbeddedBackend (llama-cpp-python)
└── factory.py             # get_backend(...), mapeo modelo -> tag/gguf
models/
├── invoice_ocr_document_line.py   # NUEVO modelo invoice.ocr.document.line
├── invoice_ocr_document.py        # MODIF: campos, enrichment, bill lines
├── res_config_settings.py         # NUEVO: config LLM
└── __init__.py                    # add imports
data/ir_cron.xml                   # NUEVO cron
views/invoice_ocr_document_views.xml   # MODIF: líneas, due_date, llm_state
views/res_config_settings_views.xml    # NUEVO
security/ir.model.access.csv           # add línea
requirements-llm.txt                   # llama-cpp-python
tests_unit/{conftest.py, test_schema.py, test_reconcile.py}   # local
tests/test_invoice_ocr_phase2.py       # Odoo (VM)
```

---

### Task 1: Migrar el harness de tests locales a sys.path

El pytest local de la capa 2 carga `extract.py` por ruta. La capa 3 tiene varios módulos con imports entre sí (`schema` usa `extract`, `reconcile` usa ambos), así que pasamos a un `conftest` que pone la raíz del módulo en `sys.path` y usa imports de paquete `lib.*`. El `__init__.py` raíz ya está protegido contra `import odoo`, así que pytest no rompe.

**Files:**
- Modify: `tests_unit/conftest.py`
- Modify: `tests_unit/test_extract.py`

- [ ] **Step 1: Reescribir `tests_unit/conftest.py`**

```python
import os
import sys

# Pone la raíz del módulo en sys.path para importar lib.* en el pytest local.
# El __init__.py raíz está protegido contra 'import odoo', así que pytest no
# arrastra los modelos de Odoo.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
```

- [ ] **Step 2: Cambiar el import en `tests_unit/test_extract.py`**

Sustituir la línea `from extract import (` por `from lib.extract import (` (el resto del import, igual).

- [ ] **Step 3: Correr la suite existente para verificar que sigue verde**

Run: `python -m pytest -q`
Expected: PASS (24 passed) — la migración no rompe la capa 2.

- [ ] **Step 4: Commit**

```bash
git add tests_unit/conftest.py tests_unit/test_extract.py
git commit -m "test: harness local por sys.path para poder importar lib.llm.*"
```

---

### Task 2: `lib/llm/prompt.py` — molde JSON + prompt

**Files:**
- Create: `lib/llm/__init__.py` (vacío), `lib/llm/prompt.py`
- Test: `tests_unit/test_prompt.py`

**Interfaces:**
- Produces: `MOLD` (dict), `SYSTEM_PROMPT` (str), `build_messages(text: str) -> list[dict]`.

- [ ] **Step 1: Crear `lib/llm/__init__.py` vacío**

```python
```

- [ ] **Step 2: Escribir el test que falla**

`tests_unit/test_prompt.py`:
```python
from lib.llm.prompt import MOLD, build_messages


def test_mold_has_expected_keys():
    assert set(MOLD.keys()) == {
        "vendor_name", "vendor_vat", "invoice_date", "invoice_ref",
        "due_date", "currency", "lines", "amount_untaxed", "amount_tax",
        "amount_total",
    }


def test_build_messages_includes_text_and_mold():
    msgs = build_messages("FACTURA X")
    assert msgs[0]["role"] == "system"
    assert "vendor_vat" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    assert "FACTURA X" in msgs[1]["content"]
```

- [ ] **Step 3: Correr para verlo fallar**

Run: `python -m pytest tests_unit/test_prompt.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lib.llm.prompt'`

- [ ] **Step 4: Implementar `lib/llm/prompt.py`**

```python
"""Molde JSON y prompt para la extracción de factura con un LLM local."""
import json

MOLD = {
    "vendor_name": None,
    "vendor_vat": None,
    "invoice_date": None,
    "invoice_ref": None,
    "due_date": None,
    "currency": None,
    "lines": [
        {"description": None, "quantity": None, "price_unit": None,
         "tax_percent": None, "amount": None}
    ],
    "amount_untaxed": None,
    "amount_tax": None,
    "amount_total": None,
}

SYSTEM_PROMPT = (
    "Eres un extractor de datos de facturas de proveedor espanolas. "
    "A partir del texto OCR, rellena EXACTAMENTE esta estructura JSON. "
    "Usa null si un dato no aparece. Importes como numeros con punto decimal "
    "(ej. 272.25). Fechas en formato YYYY-MM-DD. No inventes datos. "
    "Devuelve SOLO el JSON.\n\nEstructura:\n"
    + json.dumps(MOLD, ensure_ascii=False, indent=2)
)


def build_messages(text):
    """Mensajes chat (system + user) para el backend LLM."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "TEXTO OCR:\n" + (text or "")},
    ]
```

- [ ] **Step 5: Correr para verlo pasar**

Run: `python -m pytest tests_unit/test_prompt.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add lib/llm/__init__.py lib/llm/prompt.py tests_unit/test_prompt.py
git commit -m "feat: capa 3 prompt (molde JSON + build_messages)"
```

---

### Task 3: `lib/llm/schema.py` — normalización de la salida del modelo

**Files:**
- Create: `lib/llm/schema.py`
- Test: `tests_unit/test_schema.py`

**Interfaces:**
- Consumes: `lib.extract.parse_amount_es`.
- Produces: dataclasses `LlmLine`, `LlmInvoice`; `normalize(raw: dict) -> LlmInvoice`. Números vía `_to_float` (acepta `25.0`, `"25,00"`, `"21%"`, `"1.234,56"`); fechas vía `_to_date` (YYYY-MM-DD y dd/mm/yyyy).

- [ ] **Step 1: Escribir los tests que fallan (fixtures = salidas reales del spike)**

`tests_unit/test_schema.py`:
```python
import datetime

from lib.llm.schema import normalize, LlmInvoice

# Salida real del spike con qwen2.5:3b (numeros como strings en formato espanol)
RAW_3B = {
    "vendor_name": "HERMAFLORJARDINESYPLANTAS,S.L.",
    "vendor_vat": "07956918E",
    "invoice_date": "2026-07-13",
    "invoice_ref": "INV/2026/00048",
    "due_date": "2026-07-14",
    "currency": "EUR",
    "lines": [
        {"description": "Siega (Manual)", "quantity": "1,00", "price_unit": "25,00", "tax_percent": "21%", "amount": "25,00"},
        {"description": "Taquear", "quantity": "8,00", "price_unit": "25,00", "tax_percent": "21%", "amount": "200,00"},
    ],
    "amount_untaxed": "225,00", "amount_tax": "47,25", "amount_total": "272,25",
}

# Salida real del spike con qwen2.5:1.5b (numeros como floats, vat null)
RAW_15B = {
    "vendor_name": "HERMAFLORJARDINESYPLANTAS,S.L.",
    "vendor_vat": None,
    "invoice_date": "2026-07-13",
    "invoice_ref": "INV/2026/00048",
    "due_date": "2026-07-14",
    "currency": "EUR",
    "lines": [
        {"description": "Siega (Manual)", "quantity": 1, "price_unit": 25.0, "tax_percent": 21, "amount": 25.0},
        {"description": "Taquear", "quantity": 8, "price_unit": 25.0, "tax_percent": 21, "amount": 200.0},
    ],
    "amount_untaxed": 225.0, "amount_tax": 47.25, "amount_total": 272.25,
}


def test_normalize_3b_strings():
    inv = normalize(RAW_3B)
    assert isinstance(inv, LlmInvoice)
    assert inv.vendor_vat == "07956918E"
    assert inv.invoice_date == datetime.date(2026, 7, 13)
    assert inv.due_date == datetime.date(2026, 7, 14)
    assert inv.amount_total == 272.25
    assert len(inv.lines) == 2
    assert inv.lines[1].description == "Taquear"
    assert inv.lines[1].quantity == 8.0
    assert inv.lines[1].price_unit == 25.0
    assert inv.lines[1].tax_percent == 21.0
    assert inv.lines[1].amount == 200.0


def test_normalize_15b_floats_and_null_vat():
    inv = normalize(RAW_15B)
    assert inv.vendor_vat is None
    assert inv.amount_total == 272.25
    assert inv.lines[0].amount == 25.0
    assert inv.lines[1].tax_percent == 21.0


def test_normalize_empty():
    inv = normalize({})
    assert inv.lines == []
    assert inv.amount_total is None
```

- [ ] **Step 2: Correr para verlo fallar**

Run: `python -m pytest tests_unit/test_schema.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lib.llm.schema'`

- [ ] **Step 3: Implementar `lib/llm/schema.py`**

```python
"""Normaliza la salida (dict) del LLM a dataclasses tipadas."""
import datetime
import re
from dataclasses import dataclass, field

from ..extract import parse_amount_es


def _to_float(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    if "," in s:  # formato espanol "1.234,56"
        return parse_amount_es(s)
    s = re.sub(r"[^0-9.\-]", "", s)  # quita %, EUR, espacios
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_date(value):
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class LlmLine:
    description: "str | None" = None
    quantity: "float | None" = None
    price_unit: "float | None" = None
    tax_percent: "float | None" = None
    amount: "float | None" = None


@dataclass
class LlmInvoice:
    vendor_name: "str | None" = None
    vendor_vat: "str | None" = None
    invoice_date: "datetime.date | None" = None
    invoice_ref: "str | None" = None
    due_date: "datetime.date | None" = None
    currency: "str | None" = None
    lines: list = field(default_factory=list)
    amount_untaxed: "float | None" = None
    amount_tax: "float | None" = None
    amount_total: "float | None" = None


def normalize(raw):
    """dict crudo del LLM -> LlmInvoice. Nunca lanza; deja vacío lo que no case."""
    raw = raw or {}
    lines = []
    for item in (raw.get("lines") or []):
        if not isinstance(item, dict):
            continue
        lines.append(LlmLine(
            description=(item.get("description") or None),
            quantity=_to_float(item.get("quantity")),
            price_unit=_to_float(item.get("price_unit")),
            tax_percent=_to_float(item.get("tax_percent")),
            amount=_to_float(item.get("amount")),
        ))
    return LlmInvoice(
        vendor_name=(raw.get("vendor_name") or None),
        vendor_vat=(raw.get("vendor_vat") or None),
        invoice_date=_to_date(raw.get("invoice_date")),
        invoice_ref=(raw.get("invoice_ref") or None),
        due_date=_to_date(raw.get("due_date")),
        currency=(raw.get("currency") or None),
        lines=lines,
        amount_untaxed=_to_float(raw.get("amount_untaxed")),
        amount_tax=_to_float(raw.get("amount_tax")),
        amount_total=_to_float(raw.get("amount_total")),
    )
```

- [ ] **Step 4: Correr para verlo pasar**

Run: `python -m pytest tests_unit/test_schema.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/llm/schema.py tests_unit/test_schema.py
git commit -m "feat: capa 3 schema (normalize salida LLM a dataclasses)"
```

---

### Task 4: `lib/llm/reconcile.py` — reconciliación heurística + LLM

**Files:**
- Create: `lib/llm/reconcile.py`
- Test: `tests_unit/test_reconcile.py`

**Interfaces:**
- Consumes: `lib.extract.ExtractedInvoice`, `lib.llm.schema.LlmInvoice`.
- Produces: dataclass `MergedInvoice`; `reconcile(heur: ExtractedInvoice, llm: LlmInvoice) -> MergedInvoice`. La heurística gana en `partner_vat/invoice_date/ref/amount_*`; el LLM aporta `vendor_name/due_date/lines` y rellena huecos de la heurística.

- [ ] **Step 1: Escribir los tests que fallan**

`tests_unit/test_reconcile.py`:
```python
import datetime

from lib.extract import ExtractedInvoice
from lib.llm.schema import LlmInvoice, LlmLine
from lib.llm.reconcile import reconcile


def test_heuristic_wins_vat_and_llm_provides_lines():
    heur = ExtractedInvoice(
        partner_vat="07956918E",
        invoice_date=datetime.date(2026, 7, 13),
        ref="INV/2026/00048",
        amount_untaxed=225.0, amount_tax=47.25, amount_total=272.25,
        amounts_consistent=True,
    )
    llm = LlmInvoice(
        vendor_name="HERMAFLOR",
        vendor_vat=None,  # el 1.5B lo falla
        due_date=datetime.date(2026, 7, 14),
        lines=[LlmLine("Siega", 1.0, 25.0, 21.0, 25.0),
               LlmLine("Taquear", 8.0, 25.0, 21.0, 200.0)],
        amount_total=272.25,
    )
    m = reconcile(heur, llm)
    assert m.partner_vat == "07956918E"          # heuristica manda (LLM lo falla)
    assert m.invoice_date == datetime.date(2026, 7, 13)
    assert m.ref == "INV/2026/00048"
    assert m.amount_total == 272.25
    assert m.vendor_name == "HERMAFLOR"          # solo LLM
    assert m.due_date == datetime.date(2026, 7, 14)
    assert len(m.lines) == 2


def test_llm_fills_heuristic_gaps():
    heur = ExtractedInvoice(partner_vat=None, invoice_date=None, ref=None,
                            amount_untaxed=None, amount_tax=None, amount_total=None)
    llm = LlmInvoice(vendor_vat="B12345674", invoice_date=datetime.date(2026, 1, 2),
                     invoice_ref="F-1", amount_total=100.0, lines=[])
    m = reconcile(heur, llm)
    assert m.partner_vat == "B12345674"          # heuristica vacia -> LLM rellena
    assert m.invoice_date == datetime.date(2026, 1, 2)
    assert m.ref == "F-1"
    assert m.amount_total == 100.0
```

- [ ] **Step 2: Correr para verlo fallar**

Run: `python -m pytest tests_unit/test_reconcile.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lib.llm.reconcile'`

- [ ] **Step 3: Implementar `lib/llm/reconcile.py`**

```python
"""Fusiona el resultado determinista (heuristica) con el del LLM."""
import datetime
from dataclasses import dataclass, field


@dataclass
class MergedInvoice:
    partner_vat: "str | None" = None
    vendor_name: "str | None" = None
    invoice_date: "datetime.date | None" = None
    ref: "str | None" = None
    due_date: "datetime.date | None" = None
    amount_untaxed: "float | None" = None
    amount_tax: "float | None" = None
    amount_total: "float | None" = None
    lines: list = field(default_factory=list)


def _first(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def reconcile(heur, llm):
    """La heuristica gana en lo determinista; el LLM aporta lo difuso y huecos."""
    return MergedInvoice(
        partner_vat=_first(heur.partner_vat, llm.vendor_vat),
        vendor_name=llm.vendor_name,
        invoice_date=_first(heur.invoice_date, llm.invoice_date),
        ref=_first(heur.ref, llm.invoice_ref),
        due_date=llm.due_date,
        amount_untaxed=_first(heur.amount_untaxed, llm.amount_untaxed),
        amount_tax=_first(heur.amount_tax, llm.amount_tax),
        amount_total=_first(heur.amount_total, llm.amount_total),
        lines=list(llm.lines),
    )
```

- [ ] **Step 4: Correr para verlo pasar**

Run: `python -m pytest -q`
Expected: PASS (toda la capa 3 pura + la capa 2)

- [ ] **Step 5: Commit**

```bash
git add lib/llm/reconcile.py tests_unit/test_reconcile.py
git commit -m "feat: capa 3 reconcile (heuristica manda, LLM aporta lineas/huecos)"
```

---

### Task 5: Backends LLM (`backend_ollama.py`, `backend_embedded.py`) + `factory.py`

**Files:**
- Create: `lib/llm/backend_ollama.py`, `lib/llm/backend_embedded.py`, `lib/llm/factory.py`
- Test: `tests_unit/test_factory.py`

**Interfaces:**
- Consumes: `lib.llm.prompt.build_messages`.
- Produces: `OllamaBackend`, `EmbeddedBackend` (ambos con `extract_invoice_json(text) -> dict` y `close()`); `factory.get_backend(backend, model, models_dir=None, ollama_url=None)`; mapeos `OLLAMA_TAGS` y `GGUF_FILES` con claves `fast`/`quality`.

- [ ] **Step 1: Escribir el test que falla (mapeos, sin cargar modelos)**

`tests_unit/test_factory.py`:
```python
from lib.llm.factory import OLLAMA_TAGS, GGUF_FILES, get_backend


def test_model_maps():
    assert OLLAMA_TAGS["fast"] == "qwen2.5:1.5b"
    assert OLLAMA_TAGS["quality"] == "qwen2.5:3b"
    assert GGUF_FILES["fast"].endswith(".gguf")
    assert GGUF_FILES["quality"].endswith(".gguf")


def test_get_backend_ollama_type():
    b = get_backend(backend="ollama", model="fast", ollama_url="http://127.0.0.1:11434")
    assert b.__class__.__name__ == "OllamaBackend"
    assert b.model_id == "qwen2.5:1.5b"
```

- [ ] **Step 2: Correr para verlo fallar**

Run: `python -m pytest tests_unit/test_factory.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'lib.llm.factory'`

- [ ] **Step 3: Implementar `lib/llm/backend_ollama.py`**

```python
"""Backend LLM contra Ollama en localhost (para desarrollo y alternativa)."""
import json
import urllib.request

from .prompt import build_messages


class OllamaBackend:
    def __init__(self, model_id, url="http://127.0.0.1:11434", timeout=240):
        self.model_id = model_id
        self.url = url.rstrip("/")
        self.timeout = timeout

    def extract_invoice_json(self, text):
        payload = {
            "model": self.model_id, "stream": False, "format": "json",
            "keep_alive": "30s",
            "options": {"temperature": 0, "num_predict": 800},
            "messages": build_messages(text),
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url + "/api/chat", data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body.get("message", {}).get("content", "") or "{}"
        return json.loads(content)

    def close(self):
        pass
```

- [ ] **Step 4: Implementar `lib/llm/backend_embedded.py`**

```python
"""Backend LLM embebido con llama-cpp-python (por defecto, portable).

El modelo se carga perezoso y se libera con close(): RAM solo al procesar.
llama_cpp se importa dentro de _ensure_model para no exigirla si no se usa.
"""
from .prompt import build_messages


class EmbeddedBackend:
    def __init__(self, model_path, n_ctx=4096, n_threads=None):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self._llm = None

    def _ensure_model(self):
        if self._llm is None:
            try:
                from llama_cpp import Llama
            except ImportError as error:
                raise RuntimeError(
                    "El backend embebido requiere 'llama-cpp-python'. "
                    "Instala requirements-llm.txt o usa el backend Ollama."
                ) from error
            self._llm = Llama(
                model_path=self.model_path, n_ctx=self.n_ctx,
                n_threads=self.n_threads, verbose=False,
            )
        return self._llm

    def extract_invoice_json(self, text):
        import json
        model = self._ensure_model()
        out = model.create_chat_completion(
            messages=build_messages(text), temperature=0,
            response_format={"type": "json_object"}, max_tokens=800,
        )
        content = out["choices"][0]["message"]["content"] or "{}"
        return json.loads(content)

    def close(self):
        self._llm = None  # libera el modelo (RAM) al terminar la tanda
```

- [ ] **Step 5: Implementar `lib/llm/factory.py`**

```python
"""Fabrica de backends LLM segun configuracion."""
import os

OLLAMA_TAGS = {"fast": "qwen2.5:1.5b", "quality": "qwen2.5:3b"}
GGUF_FILES = {
    "fast": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
    "quality": "qwen2.5-3b-instruct-q4_k_m.gguf",
}


def get_backend(backend, model, models_dir=None, ollama_url=None):
    """Devuelve un backend listo para extract_invoice_json(text)."""
    if backend == "ollama":
        from .backend_ollama import OllamaBackend
        return OllamaBackend(
            model_id=OLLAMA_TAGS.get(model, OLLAMA_TAGS["fast"]),
            url=ollama_url or "http://127.0.0.1:11434",
        )
    from .backend_embedded import EmbeddedBackend
    path = os.path.join(models_dir or "", GGUF_FILES.get(model, GGUF_FILES["fast"]))
    return EmbeddedBackend(model_path=path)
```

- [ ] **Step 6: Correr para verlo pasar**

Run: `python -m pytest tests_unit/test_factory.py -q`
Expected: PASS (construir `OllamaBackend` no carga ningún modelo)

- [ ] **Step 7: Commit**

```bash
git add lib/llm/backend_ollama.py lib/llm/backend_embedded.py lib/llm/factory.py tests_unit/test_factory.py
git commit -m "feat: capa 3 backends (ollama/embedded) y factory"
```

---

### Task 6: Modelo `invoice.ocr.document.line` + campos nuevos + seguridad

**Requiere VM** para instalar/verificar.

**Files:**
- Create: `models/invoice_ocr_document_line.py`
- Modify: `models/invoice_ocr_document.py` (campos nuevos), `models/__init__.py`, `security/ir.model.access.csv`

**Interfaces:**
- Produces: modelo `invoice.ocr.document.line`; campos `line_ids`, `due_date`, `partner_name`, `llm_state`, `llm_error` en `invoice.ocr.document`.

- [ ] **Step 1: Crear `models/invoice_ocr_document_line.py`**

```python
from odoo import fields, models


class InvoiceOcrDocumentLine(models.Model):
    _name = "invoice.ocr.document.line"
    _description = "Invoice OCR Document Line"
    _order = "document_id, sequence, id"

    document_id = fields.Many2one(
        "invoice.ocr.document", required=True, ondelete="cascade"
    )
    sequence = fields.Integer(default=10)
    description = fields.Char()
    quantity = fields.Float(default=1.0)
    price_unit = fields.Float()
    tax_percent = fields.Float(string="Tax %")
    amount = fields.Float()
    product_id = fields.Many2one("product.product", string="Product")
```

- [ ] **Step 2: Añadir campos a `invoice.ocr.document`** (en `models/invoice_ocr_document.py`, junto al resto de campos)

```python
    line_ids = fields.One2many(
        "invoice.ocr.document.line", "document_id", string="Lines"
    )
    due_date = fields.Date(string="Due date")
    partner_name = fields.Char(string="Vendor name (raw)")
    llm_state = fields.Selection(
        [
            ("none", "None"),
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        default="none",
        required=True,
        index=True,
    )
    llm_error = fields.Text(string="LLM error")
```

- [ ] **Step 3: Registrar el modelo en `models/__init__.py`** (solo lo que ya existe; `res_config_settings` se añade en la Task 9)

```python
from . import invoice_ocr_document
from . import invoice_ocr_document_line
```

- [ ] **Step 4: Añadir accesos en `security/ir.model.access.csv`**

Añadir una línea:
```csv
access_invoice_ocr_document_line,invoice.ocr.document.line,model_invoice_ocr_document_line,account.group_account_invoice,1,1,1,1
```

- [ ] **Step 5: Desplegar a la VM y actualizar el módulo**

Run (VM): `sudo systemctl stop odoo && sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d test_db -u invoice_ocr --stop-after-init --workers 0 && sudo systemctl start odoo`
Expected: actualiza sin error; el modelo `invoice.ocr.document.line` existe.

- [ ] **Step 6: Commit**

```bash
git add models/invoice_ocr_document_line.py models/invoice_ocr_document.py models/__init__.py security/ir.model.access.csv
git commit -m "feat: modelo de linea OCR y campos LLM en el documento"
```

---

### Task 7: Enriquecimiento LLM en el documento (`_apply_llm_result`)

**Requiere VM** (TransactionCase). Se testea **sin modelo real**: se le pasa un `LlmInvoice` a mano.

**Files:**
- Modify: `models/invoice_ocr_document.py`
- Test: `tests/test_invoice_ocr_phase2.py`

**Interfaces:**
- Consumes: `lib.extract.extract_invoice_fields`, `lib.llm.reconcile.reconcile`, `lib.llm.schema.LlmInvoice`.
- Produces: `_apply_llm_result(self, llm_invoice)` (reconcilia con la heurística del `raw_text`, escribe `line_ids`, `due_date`, `partner_name`, rellena huecos de cabecera, casa proveedor por VAT o nombre).

- [ ] **Step 1: Escribir el test que falla**

`tests/test_invoice_ocr_phase2.py`:
```python
import datetime

from odoo.tests import TransactionCase, tagged

from odoo.addons.invoice_ocr.lib.llm.schema import LlmInvoice, LlmLine


@tagged("post_install", "-at_install")
class TestInvoiceOcrPhase2(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {"name": "Proveedor Test", "vat": "ESB12345674"}
        )

    def _doc(self, raw_text):
        att = self.env["ir.attachment"].create({"name": "t.pdf", "raw": b""})
        return self.env["invoice.ocr.document"].create(
            {"name": "t.pdf", "attachment_id": att.id, "raw_text": raw_text}
        )

    def test_apply_llm_result_writes_lines_and_fills_gaps(self):
        raw_text = "CIF B12345674\nBASE IMPONIBLE 225,00\nIVA 21% 47,25\nTOTAL 272,25\n"
        doc = self._doc(raw_text)
        llm = LlmInvoice(
            vendor_name="Proveedor Test",
            vendor_vat=None,
            due_date=datetime.date(2026, 7, 14),
            lines=[LlmLine("Siega", 1.0, 25.0, 21.0, 25.0),
                   LlmLine("Taquear", 8.0, 25.0, 21.0, 200.0)],
        )
        doc._apply_llm_result(llm)
        self.assertEqual(len(doc.line_ids), 2)
        self.assertEqual(doc.line_ids[1].description, "Taquear")
        self.assertEqual(doc.line_ids[1].amount, 200.0)
        self.assertEqual(doc.due_date, datetime.date(2026, 7, 14))
        self.assertEqual(doc.partner_id, self.partner)   # casa por VAT de la heuristica
        self.assertEqual(doc.amount_total, 272.25)        # heuristica del raw_text
```

- [ ] **Step 2: Correr para verlo fallar (VM)**

Run (VM): `sudo systemctl stop odoo && sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d test_db -u invoice_ocr --test-enable --test-tags /invoice_ocr --stop-after-init --workers 0; sudo systemctl start odoo`
Expected: FAIL con `AttributeError: ... '_apply_llm_result'`

- [ ] **Step 3: Implementar `_apply_llm_result`** (añadir a la clase, e importar reconcile)

En la cabecera del fichero, junto a `from ..lib import extract as extract_lib`, añadir:
```python
from ..lib.llm import reconcile as reconcile_lib
```

Método:
```python
    def _apply_llm_result(self, llm_invoice):
        self.ensure_one()
        heur = extract_lib.extract_invoice_fields(self.raw_text or "")
        merged = reconcile_lib.reconcile(heur, llm_invoice)
        self.line_ids.unlink()
        vals = {
            "due_date": merged.due_date,
            "partner_name": merged.vendor_name,
            "partner_vat": merged.partner_vat,
            "invoice_date": merged.invoice_date,
            "ref": merged.ref,
            "amount_untaxed": merged.amount_untaxed or 0.0,
            "amount_tax": merged.amount_tax or 0.0,
            "amount_total": merged.amount_total or 0.0,
            "line_ids": [
                (0, 0, {
                    "sequence": (index + 1) * 10,
                    "description": line.description,
                    "quantity": line.quantity or 0.0,
                    "price_unit": line.price_unit or 0.0,
                    "tax_percent": line.tax_percent or 0.0,
                    "amount": line.amount or 0.0,
                })
                for index, line in enumerate(merged.lines)
            ],
        }
        partner = self.env["res.partner"]
        if merged.partner_vat:
            partner = self._match_partner(merged.partner_vat)
        if not partner and merged.vendor_name:
            partner = self.env["res.partner"].search(
                [("name", "=", merged.vendor_name)], limit=1
            )
        if partner:
            vals["partner_id"] = partner.id
        self.write(vals)
```

- [ ] **Step 4: Correr para verlo pasar (VM)**

Run (VM): mismo comando de la Step 2.
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add models/invoice_ocr_document.py tests/test_invoice_ocr_phase2.py
git commit -m "feat: _apply_llm_result (reconcilia y escribe lineas/campos)"
```

---

### Task 8: Mapeo de líneas a `account.move` al confirmar

**Requiere VM.**

**Files:**
- Modify: `models/invoice_ocr_document.py`
- Test: `tests/test_invoice_ocr_phase2.py`

**Interfaces:**
- Modifica `_prepare_bill_vals` para usar `line_ids` cuando existan; helper `_prepare_bill_line_vals_from_line(line)`; sin crear productos; fallback a línea única del MVP.

- [ ] **Step 1: Añadir el test que falla**

En `tests/test_invoice_ocr_phase2.py`, añadir:
```python
    def test_create_bill_uses_lines_when_present(self):
        doc = self._doc("CIF B12345674\nBASE IMPONIBLE 225,00\nIVA 21% 47,25\nTOTAL 272,25\n")
        doc._apply_llm_result(LlmInvoice(
            vendor_name="Proveedor Test", vendor_vat=None,
            lines=[LlmLine("Siega", 1.0, 25.0, 21.0, 25.0),
                   LlmLine("Taquear", 8.0, 25.0, 21.0, 200.0)],
        ))
        doc.action_create_bill()
        self.assertEqual(doc.move_id.move_type, "in_invoice")
        self.assertEqual(len(doc.move_id.invoice_line_ids), 2)
        names = doc.move_id.invoice_line_ids.mapped("name")
        self.assertIn("Siega", names)
        self.assertIn("Taquear", names)
        # sin crear productos
        self.assertFalse(any(doc.move_id.invoice_line_ids.mapped("product_id")))
```

- [ ] **Step 2: Correr para verlo fallar (VM)**

Run (VM): comando de test de la Task 7 Step 2.
Expected: FAIL (crea 1 línea con el total, no 2)

- [ ] **Step 3: Modificar `_prepare_bill_vals` y añadir el helper de línea**

Sustituir el cuerpo de `_prepare_bill_vals` por:
```python
    def _prepare_bill_vals(self):
        self.ensure_one()
        if self.line_ids:
            line_cmds = [
                (0, 0, self._prepare_bill_line_vals_from_line(line))
                for line in self.line_ids
            ]
        else:
            line_cmds = [(0, 0, self._prepare_bill_line_vals())]
        return {
            "move_type": "in_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": self.invoice_date,
            "invoice_date_due": self.due_date,
            "ref": self.ref,
            "invoice_line_ids": line_cmds,
        }

    def _prepare_bill_line_vals_from_line(self, line):
        self.ensure_one()
        vals = {
            "name": line.description or _("Line"),
            "quantity": line.quantity or 1.0,
            "price_unit": line.price_unit or 0.0,
        }
        if line.product_id:
            vals["product_id"] = line.product_id.id
        tax = self.env["account.tax"].search([
            ("type_tax_use", "=", "purchase"),
            ("amount", "=", line.tax_percent or 21.0),
            ("company_id", "=", self.env.company.id),
        ], limit=1)
        if tax:
            vals["tax_ids"] = [(6, 0, tax.ids)]
        return vals
```

- [ ] **Step 4: Correr para verlo pasar (VM)**

Run (VM): comando de test de la Task 7 Step 2.
Expected: PASS (los tests de fase 2)

- [ ] **Step 5: Commit**

```bash
git add models/invoice_ocr_document.py tests/test_invoice_ocr_phase2.py
git commit -m "feat: crear factura con lineas de detalle (fallback linea unica)"
```

---

### Task 9: Configuración LLM (`res.config.settings`) + vista

**Requiere VM.**

**Files:**
- Create: `models/res_config_settings.py`, `views/res_config_settings_views.xml`
- Modify: `__manifest__.py` (data)

**Interfaces:**
- Produces: parámetros `invoice_ocr.llm_enabled`, `.llm_backend`, `.llm_model`, `.llm_models_dir`, `.llm_ollama_url`; helper de lectura `invoice.ocr.document._get_llm_backend()`.

- [ ] **Step 1: Crear `models/res_config_settings.py`**

```python
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    invoice_ocr_llm_enabled = fields.Boolean(
        string="Enable LLM enrichment",
        config_parameter="invoice_ocr.llm_enabled",
    )
    invoice_ocr_llm_backend = fields.Selection(
        [("embedded", "Embedded (llama.cpp)"), ("ollama", "Ollama (localhost)")],
        string="LLM backend", default="embedded",
        config_parameter="invoice_ocr.llm_backend",
    )
    invoice_ocr_llm_model = fields.Selection(
        [("fast", "Rapido (1.5B)"), ("quality", "Mejor (3B)")],
        string="LLM model", default="fast",
        config_parameter="invoice_ocr.llm_model",
    )
    invoice_ocr_llm_models_dir = fields.Char(
        string="Models directory (.gguf)",
        config_parameter="invoice_ocr.llm_models_dir",
    )
    invoice_ocr_llm_ollama_url = fields.Char(
        string="Ollama URL", default="http://127.0.0.1:11434",
        config_parameter="invoice_ocr.llm_ollama_url",
    )
```

Y añadir su import al final de `models/__init__.py`:
```python
from . import res_config_settings
```

- [ ] **Step 2: Añadir el helper `_get_llm_backend` a `invoice.ocr.document`**

```python
    def _get_llm_backend(self):
        from ..lib.llm import factory as llm_factory
        params = self.env["ir.config_parameter"].sudo()
        return llm_factory.get_backend(
            backend=params.get_param("invoice_ocr.llm_backend", "embedded"),
            model=params.get_param("invoice_ocr.llm_model", "fast"),
            models_dir=params.get_param("invoice_ocr.llm_models_dir", ""),
            ollama_url=params.get_param("invoice_ocr.llm_ollama_url", "http://127.0.0.1:11434"),
        )
```

- [ ] **Step 3: Crear `views/res_config_settings_views.xml`**

```xml
<odoo>
    <record id="res_config_settings_view_form_invoice_ocr" model="ir.ui.view">
        <field name="name">res.config.settings.invoice.ocr</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="account.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//block[last()]" position="after">
                <block title="Invoice OCR (LLM)" id="invoice_ocr_llm_block">
                    <setting string="Enrichment con LLM local" help="Extrae lineas de detalle con un modelo local, en segundo plano.">
                        <field name="invoice_ocr_llm_enabled"/>
                        <div invisible="not invoice_ocr_llm_enabled">
                            <field name="invoice_ocr_llm_backend"/>
                            <field name="invoice_ocr_llm_model"/>
                            <field name="invoice_ocr_llm_models_dir"
                                   invisible="invoice_ocr_llm_backend != 'embedded'"/>
                            <field name="invoice_ocr_llm_ollama_url"
                                   invisible="invoice_ocr_llm_backend != 'ollama'"/>
                        </div>
                    </setting>
                </block>
            </xpath>
        </field>
    </record>
</odoo>
```

- [ ] **Step 4: Añadir la vista a `__manifest__.py` (`data`)**

Añadir `'views/res_config_settings_views.xml'` a la lista `data` (tras las vistas del documento).

- [ ] **Step 5: Actualizar el módulo en la VM y verificar los ajustes**

Run (VM): `sudo systemctl stop odoo && sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d test_db -u invoice_ocr --stop-after-init --workers 0 && sudo systemctl start odoo`
Expected: actualiza sin error; en Contabilidad → Ajustes aparece el bloque "Invoice OCR (LLM)".

- [ ] **Step 6: Commit**

```bash
git add models/res_config_settings.py views/res_config_settings_views.xml __manifest__.py
git commit -m "feat: ajustes LLM (backend, modelo, rutas) y _get_llm_backend"
```

---

### Task 10: Marcar `pending` al subir + `ir.cron` de enriquecimiento

**Requiere VM.**

**Files:**
- Modify: `models/invoice_ocr_document.py`
- Create: `data/ir_cron.xml`
- Modify: `__manifest__.py` (data)

**Interfaces:**
- Consumes: `_get_llm_backend`, `schema.normalize`, `_apply_llm_result`.
- Produces: `action_process` marca `llm_state = pending` si `llm_enabled`; `_cron_llm_enrichment(limit=20)` (carga backend una vez, procesa la tanda, libera).

- [ ] **Step 1: Marcar `pending` en `action_process`** (al final del bucle, tras `_apply_extraction`)

Sustituir el cuerpo de `action_process` por:
```python
    def action_process(self):
        llm_enabled = self.env["ir.config_parameter"].sudo().get_param(
            "invoice_ocr.llm_enabled"
        )
        for document in self:
            try:
                document.state = "processing"
                text = document._ocr_text()
                document._apply_extraction(text)
                if llm_enabled:
                    document.llm_state = "pending"
            except Exception as error:  # noqa: BLE001 - se refleja en el registro
                document.state = "error"
                document.error_message = str(error)
        return True
```

- [ ] **Step 2: Añadir el método de cron** (a la clase)

```python
    def _cron_llm_enrichment(self, limit=20):
        from ..lib.llm import schema as schema_lib
        docs = self.search([("llm_state", "=", "pending")], limit=limit)
        if not docs:
            return
        backend = docs[:1]._get_llm_backend()
        try:
            for document in docs:
                try:
                    document.llm_state = "processing"
                    raw = backend.extract_invoice_json(document.raw_text or "")
                    document._apply_llm_result(schema_lib.normalize(raw))
                    document.llm_state = "done"
                except Exception as error:  # noqa: BLE001
                    document.llm_state = "error"
                    document.llm_error = str(error)
                self.env.cr.commit()
        finally:
            backend.close()
```

- [ ] **Step 3: Crear `data/ir_cron.xml`**

```xml
<odoo>
    <record id="ir_cron_invoice_ocr_llm" model="ir.cron">
        <field name="name">Invoice OCR: enriquecimiento LLM</field>
        <field name="model_id" ref="model_invoice_ocr_document"/>
        <field name="state">code</field>
        <field name="code">model._cron_llm_enrichment()</field>
        <field name="interval_number">5</field>
        <field name="interval_type">minutes</field>
        <field name="active" eval="False"/>
    </record>
</odoo>
```

- [ ] **Step 4: Añadir `data/ir_cron.xml` a `__manifest__.py` (`data`)**

- [ ] **Step 5: Actualizar en la VM y verificar el flujo con el backend Ollama**

Run (VM): actualizar módulo; activar `invoice_ocr.llm_enabled=1`, `llm_backend=ollama`, `llm_model=fast` en Ajustes; por `odoo shell`: coger un documento con `raw_text`, `doc.llm_state='pending'`, `self.env['invoice.ocr.document']._cron_llm_enrichment()`, comprobar `doc.line_ids` y `doc.llm_state=='done'`.
Expected: se crean las líneas vía LLM.

- [ ] **Step 6: Commit**

```bash
git add models/invoice_ocr_document.py data/ir_cron.xml __manifest__.py
git commit -m "feat: cron de enriquecimiento LLM (cargar/procesar/liberar) y marca pending"
```

---

### Task 11: Vistas — líneas, vencimiento y estado LLM en el formulario

**Requiere VM** (verificación de UI a mano).

**Files:**
- Modify: `views/invoice_ocr_document_views.xml`

- [ ] **Step 1: Añadir al formulario los campos y la tabla de líneas**

En el `<group>` derecho del formulario, tras `move_id`, añadir:
```xml
                            <field name="due_date"/>
                            <field name="partner_name"/>
                            <field name="llm_state" widget="badge"
                                   decoration-info="llm_state == 'processing'"
                                   decoration-success="llm_state == 'done'"
                                   decoration-danger="llm_state == 'error'"/>
```
Y en el `<notebook>`, antes de la página "Texto OCR", añadir:
```xml
                        <page string="Lineas">
                            <field name="line_ids">
                                <list editable="bottom">
                                    <field name="sequence" widget="handle"/>
                                    <field name="description"/>
                                    <field name="quantity"/>
                                    <field name="price_unit"/>
                                    <field name="tax_percent"/>
                                    <field name="amount"/>
                                    <field name="product_id"/>
                                </list>
                            </field>
                        </page>
                        <page string="LLM" invisible="llm_state == 'none'">
                            <field name="llm_error" readonly="1"/>
                        </page>
```

- [ ] **Step 2: Actualizar en la VM y verificar a mano**

Run (VM): actualizar módulo; abrir un documento: se ven la pestaña "Lineas" (editable), `due_date`, y el badge de `llm_state`.
Expected: UI correcta, sin errores de XML.

- [ ] **Step 3: Commit**

```bash
git add views/invoice_ocr_document_views.xml
git commit -m "feat: formulario con lineas, vencimiento y estado LLM"
```

---

### Task 12: Empaquetado — `requirements-llm.txt` + prueba de humo del backend embebido

**Requiere VM.**

**Files:**
- Create: `requirements-llm.txt`
- Modify: `install.sh`, `install.ps1` (nota del extra LLM)

- [ ] **Step 1: Crear `requirements-llm.txt`**

```
llama-cpp-python
huggingface-hub
```

- [ ] **Step 2: Añadir nota en `install.sh` e `install.ps1`**

Añadir al final de cada script un comentario/echo indicando que, para el enriquecimiento LLM con el backend embebido, hay que instalar además `requirements-llm.txt` y descargar los `.gguf` al `llm_models_dir`.

`install.sh` (añadir):
```sh
echo "LLM (opcional, backend embebido): $PYTHON -m pip install -r $(dirname "$0")/requirements-llm.txt ; y descarga los .gguf al models dir."
```

- [ ] **Step 3: Prueba de humo del backend embebido en la VM**

Instalar en la VM: `sudo python3 -m pip install --break-system-packages llama-cpp-python huggingface-hub`; descargar un `.gguf` 1.5B (`huggingface-cli download Qwen/Qwen2.5-1.5B-Instruct-GGUF qwen2.5-1.5b-instruct-q4_k_m.gguf --local-dir /opt/gguf`); luego un script Python que instancie `EmbeddedBackend(model_path=...)` y llame `extract_invoice_json(texto_real)`.
Expected: devuelve el dict con líneas (misma calidad que Ollama). Nota: en esta VP la CPU es lenta; la prueba confirma funcionalidad, no velocidad.

- [ ] **Step 4: Commit**

```bash
git add requirements-llm.txt install.sh install.ps1
git commit -m "chore: requirements-llm y nota de setup del backend embebido"
```

---

### Task 13: Test de integración completo + regresión de fase 1

**Requiere VM.**

**Files:**
- Modify: `tests/test_invoice_ocr_phase2.py` (si hace falta consolidar)

- [ ] **Step 1: Correr TODA la suite (local + Odoo)**

Run (local): `python -m pytest -q` → toda la capa 2 y 3 pura en verde.
Run (VM): `sudo systemctl stop odoo && sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d test_db -u invoice_ocr --test-enable --test-tags /invoice_ocr --stop-after-init --workers 0; sudo systemctl start odoo`
Expected: `0 failed, 0 error(s)` (fase 1 + fase 2).

- [ ] **Step 2: Commit (si hubo ajustes)**

```bash
git add -A
git commit -m "test: suite completa fase 1 + fase 2 en verde"
```

---

## Self-Review (cobertura del spec)

- Flujo dos tiempos + reconciliación: Tareas 3, 4, 7, 10. ✔
- Capa 3 tras interfaz (prompt/schema/reconcile/backends/factory): Tareas 2-5. ✔
- Backend embebido por defecto + Ollama alternativo: Task 5, 12. ✔
- Modelo seleccionable 1.5B/3B: Task 5 (mapeos) + Task 9 (config). ✔
- Datos (`invoice.ocr.document.line`, `due_date`, `partner_name`, `llm_state`): Task 6. ✔
- Líneas → `account.move` sin crear productos + fallback: Task 8. ✔
- Cron cargar→procesar→liberar sin queue_job: Task 10. ✔
- Config (enabled/backend/model/dir/url): Task 9. ✔
- UI (líneas, due_date, llm_state): Task 11. ✔
- Empaquetado (`llama_cpp` blanda, `.gguf` fuera de git): Task 12. ✔
- TDD capa 3 pura con fixtures reales del spike: Tareas 3, 4. ✔
- Nombres/firmas consistentes (`extract_invoice_json`, `normalize`, `reconcile`, `MergedInvoice`, `LlmInvoice`, `_apply_llm_result`, `_get_llm_backend`, `_cron_llm_enrichment`): revisado. ✔

Fuera de alcance por diseño (no huecos): albaranes, buzón email, Escáner Modernist, auto-categorización, pedido de compra, creación de productos, manuscrito.
