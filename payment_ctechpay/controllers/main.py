# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import os
from typing import Any, Dict, Optional
from decimal import Decimal

import requests
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


class CTechPayController(Controller):
    _process_url = '/payment/ctechpay/process'
    _return_url = '/payment/ctechpay/return'

    @staticmethod
    def _extract_redirect_url(payload: Any) -> Optional[str]:
        if not payload:
            return None
        if isinstance(payload, str):
            return payload if payload.startswith('http') else None
        if not isinstance(payload, dict):
            return None
        # Laravel sample expects 'payment_page_URL'
        for key in ('payment_page_URL', 'payment_page_url'):
            val = payload.get(key)
            if isinstance(val, str) and val.startswith('http'):
                return val
        # Fallbacks
        for key in ('checkout_url', 'redirectUrl', 'redirect_url', 'url', 'payment_url', 'link'):
            val = payload.get(key)
            if isinstance(val, str) and val.startswith('http'):
                return val
        nested = payload.get('data')
        if isinstance(nested, dict):
            return CTechPayController._extract_redirect_url(nested)
        return None

    @route(_process_url, type='http', auth='public', methods=['POST'], csrf=False)
    def ctechpay_process_transaction(self, **post):
        reference = post.get('reference')
        if not reference:
            _logger.error('CTechPay: missing reference in process payload: %s', post)
            return request.redirect('/payment/status')
        tx = request.env['payment.transaction'].sudo().search([('reference', '=', reference)], limit=1)
        if not tx or tx.provider_code != 'ctechpay':
            _logger.error('CTechPay: transaction not found/mismatch for reference %s', reference)
            return request.redirect('/payment/status')

        provider = tx.provider_id.sudo()
        token = provider.ctechpay_api_token
        if not token:
            _logger.error('CTechPay: token is not configured on provider %s', provider.id)
            return request.redirect('/payment/status')

        # Compare with ENV token as a sanity check (do not log full secrets)
        env_token = os.getenv('CTECHPAY_API_TOKEN')
        if env_token and env_token != token:
            _logger.warning('CTechPay: provider token differs from environment token (using provider token).')

        # Build a robust base URL that works with ngrok and avoids double slashes
        # Priority: WEB_BASE_URL env -> current request host -> provider base URL
        base_url = os.getenv('WEB_BASE_URL') or (request.httprequest.url_root if request else None) or provider.get_base_url()
        if base_url:
            base_url = base_url.strip().rstrip('/')
            # If it's an ngrok domain but scheme is http, force https
            if base_url.startswith('http://') and '.ngrok' in base_url:
                base_url = 'https://' + base_url[len('http://'):]
            # Localhost/dev fallbacks: allow override via NGROK_BASE_URL if provided
            if '127.0.0.1' in base_url or 'localhost' in base_url:
                fallback = os.getenv('NGROK_BASE_URL') or os.getenv('WEB_BASE_URL')
                if fallback:
                    base_url = fallback.strip().rstrip('/')
        # Use a dedicated return endpoint to come back to Odoo, which then shows status
        redirect_url = f"{base_url}/payment/ctechpay/return"
        _logger.info('CTechPay redirect URL: %s', redirect_url)

        url = 'https://api-gateway.ctechpay.com/?endpoint=order'
        # Per CTechPay docs, minimum required form fields are token and amount.
        # Amount must be an integer (e.g., 100). We'll send the integer part of the transaction amount.
        amount_str = str(int(Decimal(str(tx.amount)).quantize(Decimal('1'))))
        # Send as multipart/form-data per provider requirements
        return_url = f"{base_url}/payment/ctechpay/return"
        cancel_url = f"{base_url}/payment/ctechpay/return?status=cancel"
        files_payload = {
            'token': (None, token),
            'amount': (None, amount_str),
            'redirectUrl': (None, return_url),
            'cancelUrl': (None, cancel_url),
        }
        headers = {
            'Accept': '*/*',
            'User-Agent': 'curl/8.5.0',
            'endpoint': 'order',
            # Do NOT set Content-Type manually when using files=; requests will include the proper boundary
        }
        # Some providers are picky; trim whitespace from token just in case
        files_payload['token'] = (None, (token or '').strip())
        try:
            response = requests.post(url, files=files_payload, headers=headers, timeout=30, verify=False)
            if response.status_code == 403:
                # Fallback: try classic application/x-www-form-urlencoded
                form_payload = {
                    'token': (token or '').strip(),
                    'amount': amount_str,
                }
                _logger.info('CTechPay: multipart returned 403, retrying with form-encoded...')
                response = requests.post(url, data=form_payload, headers={'Accept': 'application/json'}, timeout=30, verify=False)
            text = response.text or ''
            try:
                data = response.json()
            except Exception:
                try:
                    data = json.loads(text)
                except Exception:
                    data = text
        except Exception as e:
            _logger.exception('CTechPay API error (order): %s', e)
            return request.redirect('/payment/status')

        # Log status and small sample for troubleshooting
        sample = data if isinstance(data, (dict, list)) else (str(data)[:400] + '...')
        _logger.info('CTechPay order response (status=%s): %s', response.status_code, sample)

        payment_page_url = self._extract_redirect_url(data)
        if payment_page_url:
            # Normalize payment URL to avoid relative redirects back to Odoo
            url_str = (payment_page_url or '').strip()
            if url_str and not url_str.lower().startswith(('http://', 'https://')):
                # Handle cases like '?code=...' or missing scheme
                if 'paypage.standardbank.co.mw' in url_str:
                    if not url_str.lower().startswith(('http://', 'https://')):
                        url_str = 'https://' + url_str.lstrip('/')
                elif url_str.startswith('?code='):
                    url_str = 'https://paypage.standardbank.co.mw/' + url_str
            # Extra safety: collapse accidental spaces in domain
            url_str = url_str.replace('paypage.    standardbank', 'paypage.standardbank')
            return request.redirect(url_str, local=False)

        error = None
        if isinstance(data, dict):
            status = data.get('status')
            if isinstance(status, dict):
                error = status.get('message') or status.get('error')
            error = error or data.get('message') or data.get('error')
        _logger.error('CTechPay API returned no redirect URL. Error: %s | Data: %s', error, sample)
        return request.redirect('/payment/status')
