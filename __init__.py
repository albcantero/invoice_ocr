try:
    import odoo  # noqa: F401
except ImportError:
    # Fuera de Odoo (p. ej. el pytest local de la capa 2) no existe 'odoo';
    # el paquete se importa igual, sin cargar los modelos.
    pass
else:
    from . import models
    from . import wizards
