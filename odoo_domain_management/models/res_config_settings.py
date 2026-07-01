# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    """Extend general settings to configure the Domainrobot API credentials."""

    _inherit = 'res.config.settings'

    # ── API configuration fields ──────────────────────────────────────────────

    domainrobot_api_url = fields.Char(
        string='API Endpoint URL',
        default='https://api.domainreselling.de/api/call.cgi',
        config_parameter='domainrobot.api_url',
        help='Base URL of the Domainrobot/united-domains Reselling API.',
    )
    domainrobot_api_user = fields.Char(
        string='API Username (s_login)',
        config_parameter='domainrobot.api_user',
        help='Login name for the Domainrobot API.',
    )
    domainrobot_api_password = fields.Char(
        string='API Password (s_pw)',
        ******
        config_parameter='domainrobot.api_password',
        help='Password / token for the Domainrobot API. Stored as a system parameter.',
    )
    domainrobot_api_timeout = fields.Integer(
        string='API Timeout (seconds)',
        default=30,
        config_parameter='domainrobot.api_timeout',
        help='HTTP request timeout in seconds.',
    )
