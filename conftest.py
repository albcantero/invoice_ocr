import os
import sys

# Permite `from lib.extract import ...` al correr pytest en local (capa 2),
# sin arrastrar Odoo ni rapidocr.
sys.path.insert(0, os.path.dirname(__file__))
