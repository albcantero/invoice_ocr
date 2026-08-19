#!/usr/bin/env sh
# Instala las dependencias Python de invoice_ocr en el Python de Odoo.
# Uso: ./install.sh [ruta/al/python-de-odoo]   (por defecto: python3)
set -e
PYTHON="${1:-python3}"
"$PYTHON" -m pip install -r "$(dirname "$0")/requirements.txt"

echo "LLM (opcional, backend embebido): $PYTHON -m pip install -r $(dirname "$0")/requirements-llm.txt ; y descarga los .gguf al models dir."
