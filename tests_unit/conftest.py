import os
import sys

# Pone la raíz del módulo en sys.path para importar lib.* en el pytest local.
# El __init__.py raíz está protegido contra 'import odoo', así que pytest no
# arrastra los modelos de Odoo.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
