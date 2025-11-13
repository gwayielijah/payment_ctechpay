# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Payment Provider: CTechPay',
    'version': '1.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 351,
    'summary': 'CTechPay payment gateway (credit card redirect)',
    'description': 'Minimal server-driven redirect flow to CTechPay payment page.',
    'depends': ['payment'],
    'data': [
        'views/payment_ctechpay_templates.xml',
        'views/payment_provider_views.xml',
        #'data/payment_provider_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'post_load': 'post_load',
    'license': 'LGPL-3',
    'author': 'CtechPay',
}
