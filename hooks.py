# Part of Odoo. See LICENSE file for full copyright and licensing details.
import os
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# Hardcoded token fallback
ENV_VAR_NAME = "CTECHPAY_API_TOKEN"
HARDCODED_TOKEN = 'frEV25jRXZAxDgVyhZTH5boJwQbOMMMb2idv9hv3xJd4Dikq0xa8zoDb3rAn8xkQeV0BsPOc3Zos0NTwSLXPA=='

def _apply_token(env):
    """Set the CTechPay token from environment or fallback hardcoded token."""
    # Ensure model exists
    try:
        Provider = env["payment.provider"].sudo()
    except Exception:  # model not in registry
        _logger.info("CTechPay: payment.provider model not available; skipping token bootstrap")
        return

    # Ensure 'code' field exists
    try:
        if "code" not in Provider._fields:
            _logger.info("CTechPay: payment.provider.code field not available; skipping token bootstrap")
            return
    except Exception:
        _logger.info("CTechPay: unable to inspect provider fields; skipping token bootstrap")
        return

    # Ensure the provider exists, create it if missing
    provider = Provider.search([("code", "=", "ctechpay")], limit=1)
    if not provider:
        _logger.info("CTechPay: provider not found; creating it...")
        provider = Provider.create({
            "name": "CTechPay",
            "code": "ctechpay",
            "state": "disabled",
        })

    # Apply token from environment or hardcoded
    token = os.getenv(ENV_VAR_NAME) or HARDCODED_TOKEN

    if getattr(provider, "ctechpay_api_token", None):
        _logger.info("CTechPay: provider already has a token; not overwriting")
        return

    try:
        provider.write({"ctechpay_api_token": token})
        _logger.info("CTechPay: token bootstrapped from environment variable %s", ENV_VAR_NAME)
    except Exception as e:
        _logger.exception("CTechPay: failed to write token to provider: %s", e)

# In Odoo 17/19, post_init_hook receives env
def post_init_hook(env):
    _apply_token(env)

def post_load():
    from odoo.service import db as service_db  # lazy import
    from odoo.modules.registry import Registry

    db_names = service_db.list_dbs() or []
    for dbname in db_names:
        registry = Registry(dbname)
        try:
            with registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                _apply_token(env)
        except Exception:
            _logger.exception("CTechPay: error while applying token in post_load for DB %s", dbname)
