import importlib.util
import os
import sys

# Carga lib/extract.py por ruta directa como módulo "extract", sin tocar
# sys.path ni importar el paquete Odoo de la raíz (que importa odoo).
_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "lib", "extract.py")
)
_spec = importlib.util.spec_from_file_location("extract", _path)
_module = importlib.util.module_from_spec(_spec)
# Registrar antes de ejecutar: el @dataclass con anotaciones string necesita
# encontrar su propio módulo en sys.modules durante la definición de la clase.
sys.modules["extract"] = _module
_spec.loader.exec_module(_module)
