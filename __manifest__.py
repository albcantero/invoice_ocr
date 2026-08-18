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
    ],
    'application': True,
    'installable': True,
}
