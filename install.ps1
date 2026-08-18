# Instala las dependencias Python de invoice_ocr en el Python de Odoo.
# Uso: .\install.ps1 -Python C:\ruta\a\python.exe
param([string]$Python = "python")
& $Python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
