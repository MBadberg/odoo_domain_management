# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class DomainAccount(models.Model):
    """Represents reseller account information, balance, and pricing snapshot."""

    _name = 'domain.account'
    _description = 'Domain Account & Pricing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Account', default='Main Account', required=True, tracking=True)
    reseller_name = fields.Char(string='Reseller Name')
    provider = fields.Char(string='Provider', default='Domainrobot / united-domains')
    balance = fields.Float(string='Balance', default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency')
    last_sync = fields.Datetime(string='Last Sync', readonly=True)
    account_status = fields.Text(string='Account Status', readonly=True)
    pricing_snapshot = fields.Text(string='Pricing Snapshot', readonly=True)
    api_response_code = fields.Char(string='API Response Code', readonly=True)
    api_response_message = fields.Text(string='API Response Message', readonly=True)

    def _get_client(self):
        from odoo.addons.odoo_domain_management.services.domainrobot_client import DomainrobotClient
        return DomainrobotClient.from_system_params(self.env)

    def action_sync_account(self):
        """Fetch account status and keep a simple pricing snapshot in the backend."""
        self.ensure_one()
        client = self._get_client()
        result = client.status_user()
        properties = result.get('properties', {}) or {}
        balance = 0.0
        if properties.get('BALANCE'):
            try:
                balance = float(properties['BALANCE'][0])
            except (TypeError, ValueError, IndexError):
                balance = 0.0

        self.write({
            'api_response_code': result.get('code', ''),
            'api_response_message': result.get('description', ''),
            'account_status': result.get('description', '') or '',
            'last_sync': fields.Datetime.now(),
            'balance': balance,
            'pricing_snapshot': json.dumps(properties, indent=2, sort_keys=True, ensure_ascii=False) if properties else '',
        })
        self.message_post(body=_('Account and pricing data synced from the Domainrobot API.'))
        return True
