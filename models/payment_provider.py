# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('ctechpay', 'CTechPay')], ondelete={'ctechpay': 'set default'}
    )
    ctechpay_api_token = fields.Char(
        string='CTechPay API Token',
        required_if_provider='ctechpay',
        copy=False,
        groups='base.group_system',
    )

    def _get_default_payment_method_codes(self):
        self.ensure_one()
        if self.code != 'ctechpay':
            return super()._get_default_payment_method_codes()
        # Only card for now (server-driven redirect)
        return {'card'}
