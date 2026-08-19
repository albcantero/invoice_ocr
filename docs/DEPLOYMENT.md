# invoice_ocr — Despliegue y operaciones

Registro completo de **lo que necesita el módulo, cómo se instala, cómo se opera y cómo se retira**, basado en la puesta en marcha real sobre la VM de desarrollo (Ubuntu 24.04, Odoo 19 instalado como paquete `.deb`, servicio `odoo` como usuario `odoo`, config `/etc/odoo/odoo.conf`, addons custom en `/opt/custom_addons`).

---

## 1. Dependencias

### Python (en el intérprete con el que corre Odoo)
| Para | Paquetes (`pip`) | Fichero |
|---|---|---|
| Núcleo OCR + PDF | `rapidocr-onnxruntime`, `PyMuPDF` | `requirements.txt` |
| LLM embebido (fase 2) | `llama-cpp-python`, `huggingface-hub` | `requirements-llm.txt` |

- Sin **binarios de sistema** para el núcleo: `rapidocr` (ONNX) y `PyMuPDF` son *wheels*. **No** hacen falta Tesseract ni poppler.
- `llama-cpp-python` en CPU, con *wheel* precompilada (evita compilar):
  `pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`
- Odoo es paquete deb → usa el **Python del sistema** (`/usr/bin/python3`), sin venv. Instalación con `--break-system-packages` (PEP 668).

### Sistema (apt, Debian/Ubuntu)
- `python3-pip` (si el Python de Odoo no trae pip).
- `libgl1`, `libglib2.0-0` → los pide **opencv** (dependencia de `rapidocr`) en servidor *headless*; sin ellos: `ImportError: libGL.so.1`.
- Solo si `llama-cpp-python` **compila desde fuente** (sin wheel): `build-essential`, `python3-dev`, `cmake`. Con la wheel precompilada **no** hacen falta.

---

## 2. Instalación del módulo
1. Copiar el módulo a la ruta de addons (`/opt/custom_addons/invoice_ocr`), legible por el usuario `odoo`.
2. Instalar dependencias (§1). Scripts `install.sh` / `install.ps1` para el núcleo; `requirements-llm.txt` para el LLM embebido.
3. Instalar el módulo desde Odoo (categoría Contabilidad). Menú: **Contabilidad → Escáner de facturas**.

**Nota (obligatoria):** el módulo es `application`, y Odoo renderiza su descripción; necesita `static/description/index.html` o falla al instalar con un error de `docutils`. Ya está incluido.

---

## 3. LLM — backend Ollama (recomendado; único camino a GPU en red)
- Instalar: `curl -fsSL https://ollama.com/install.sh | sh` → crea servicio systemd en `127.0.0.1:11434`.
- Modelos: `ollama pull qwen2.5:1.5b` (rápido) / `ollama pull qwen2.5:3b` (mejor calidad de líneas).
- Ajustes del módulo: **backend = Ollama**, URL, modelo (Rápido 1.5B / Mejor 3B).
- **GPU en otra máquina** (p. ej. Odoo en una VM sin GPU, GPU en el host): arranca Ollama en la máquina con GPU con `OLLAMA_HOST=0.0.0.0` (+ abrir el 11434 en firewall) y pon la URL del módulo apuntando a su IP. Ollama usa la GPU (NVIDIA/AMD) sola.

## 4. LLM — backend embebido (`llama-cpp-python`, en proceso, portable)
- `pip install -r requirements-llm.txt` + descargar el `.gguf` al **models dir** (Ajustes), p. ej. `/opt/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf` (con `huggingface_hub.hf_hub_download`).
- **El `.gguf` (y su carpeta) debe ser legible por el usuario `odoo`**: `chmod -R a+rX /opt/gguf`.
- **Subir los límites de memoria por worker de Odoo** (el modelo se carga *dentro* del worker); si no → `Failed to create llama_context` (aunque sobre RAM: es el tope de *espacio de direcciones* del worker). En `/etc/odoo/odoo.conf`:
  ```ini
  limit_memory_soft = 5368709120   ; 5 GB
  limit_memory_hard = 6442450944   ; 6 GB
  ```
  y reiniciar Odoo.
- El embebido **solo va a GPU** si el build es CUDA (`-DGGML_CUDA=on` / wheel `cuXXX`) y se pasa `n_gpu_layers`, **y la GPU está en la misma máquina que Odoo**. Para una GPU en otra máquina → usar Ollama en red (§3).

---

## 5. Rendimiento (medido)
| Entorno | Modelo | Tiempo por factura |
|---|---|---|
| CPU (VM 4 vCPU, sin GPU) | 1.5B | ~1 min (en segundo plano) |
| GPU (NVIDIA RTX 4060 Ti, Ollama) | 1.5B | **~1,5 s en caliente** (~200 tok/s) |

- El LLM corre en `ir.cron` (patrón **cargar → procesar tanda → liberar**; RAM solo al procesar). La **cabecera (heurística) es instantánea**; las líneas se rellenan después.
- Conclusión: nivel "Holded" (~2 s) es alcanzable **local y sin API** con una GPU modesta. En CPU es escala de minutos → pensado para **lotes en background**, no para mirarlo en directo.

---

## 6. Retirada (revert completo de la VM)
```bash
# 1) Desinstalar el módulo de la BD (con los ficheros aún presentes)
sudo -u odoo /usr/bin/odoo shell -c /etc/odoo/odoo.conf -d <db> --no-http <<'PY'
m = env['ir.module.module'].search([('name','=','invoice_ocr')])
if m and m.state != 'uninstalled': m.button_immediate_uninstall()
env.cr.commit()
PY
# 2) Quitar los ficheros del addon
sudo rm -rf /opt/custom_addons/invoice_ocr
# 3) Ollama + modelos
sudo systemctl disable --now ollama
sudo rm -f /usr/local/bin/ollama /etc/systemd/system/ollama.service
sudo systemctl daemon-reload
sudo rm -rf /usr/share/ollama          # binario/home + modelos descargados
sudo userdel ollama
sudo rm -rf /opt/gguf                   # gguf del backend embebido
# 4) Dependencias Python
sudo python3 -m pip uninstall -y --break-system-packages \
  rapidocr-onnxruntime onnxruntime opencv-python opencv-python-headless \
  pyclipper shapely PyMuPDF llama-cpp-python huggingface-hub diskcache
# 5) Revertir odoo.conf (workers / limit_memory) y reiniciar
sudo cp /etc/odoo/odoo.conf.bak /etc/odoo/odoo.conf   # backup hecho antes de tocar
sudo systemctl restart odoo
```
Nota: los apt `libgl1`, `libglib2.0-0`, `python3-pip` y las build-tools son **librerías compartidas del sistema**; conviene dejarlas (quitarlas puede romper otras cosas). `sudo apt-get autoremove` limpia solo lo huérfano.

---

## 7. Aprendizajes (gotchas reales de esta puesta en marcha)
- **`static/description/index.html`** obligatorio o `docutils` peta al instalar (módulo `application`).
- El **`__init__.py` raíz protege `import odoo`** para que el `pytest` local de la capa pura no arrastre Odoo.
- Los **tests unitarios de la capa pura** (capa 2 heurística, capa 3 LLM) van en `tests_unit/` por `sys.path`, **separados** del paquete `tests/` de Odoo.
- El **OCR pega etiqueta+valor** ("Fecha18/07/2026") y pone **importes en columna** → regex con *lookbehind* (no `\b`) y `find_amounts` mira la línea siguiente.
- **Embebido**: choca con el límite de memoria del worker de Odoo (`RLIMIT_AS`) aunque sobre RAM física → subir `limit_memory_*`.
- Un **modelo pequeño (1.5B) descuadra líneas** a veces → el **gate de coherencia** (suma de líneas vs base heurística) cae a **línea única** para no ensuciar la factura.
- El **14700KF no tiene iGPU** → si hay salida de vídeo, hay GPU dedicada; se puede aprovechar con Ollama en red aunque Odoo esté en una VM sin GPU.
