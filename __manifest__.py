{
    'name': 'Invoice OCR',
    'version': '19.0.1.0.0',
    'summary': 'Escáner de facturas de proveedor con OCR local, sin API',
    'author': 'Alberto Cantero',
    'website': 'https://github.com/albcantero/invoice_ocr',
    'license': 'LGPL-3',
    'category': 'Accounting',
    'depends': ['account'],
    # Sin dependencias externas: lectura de PDF con pypdf/PyPDF2 (ya en Odoo)
    # y render del editor con pdf.js (ya en Odoo). Plug-and-play.
    'data': [
        'security/ir.model.access.csv',
        # Capa LLM (fase beta) PARKEADA — reponer estas 2 lineas para reactivar:
        # 'data/ir_cron.xml',
        'views/invoice_ocr_document_views.xml',
        'views/invoice_ocr_template_views.xml',
        'wizards/invoice_ocr_upload_views.xml',
        'views/invoice_ocr_menus.xml',
        # 'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'invoice_ocr/static/src/js/template_editor.js',
            'invoice_ocr/static/src/xml/template_editor.xml',
        ],
    },
    'application': True,
    'installable': True,
}
