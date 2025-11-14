# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models

from odoo.addons.payment_ctechpay.controllers.main import CTechPayController


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        # Note: self.ensure_one() from _get_processing_values
        if self.provider_code != 'ctechpay':
            return super()._get_specific_rendering_values(processing_values)
        # Server-driven: post the reference to our process endpoint which will create
        # the CTechPay order and redirect to the URL returned by the API.
        return {
            'api_url': CTechPayController._process_url,
            'reference': self.reference,
        }
