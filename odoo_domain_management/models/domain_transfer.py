# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class DomainTransfer(models.Model):
    """Represents a domain transfer request or status report."""

    _name = 'domain.transfer'
    _description = 'Domain Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'transfer_date desc, name'

    name = fields.Char(string='Domain', required=True, tracking=True)
    domain_id = fields.Many2one(
        'domain.asset',
        string='Managed Domain',
        ondelete='set null',
        tracking=True,
    )
    partner_id = fields.Many2one('res.partner', string='Customer', tracking=True)
    transfer_type = fields.Selection(
        [('incoming', 'Incoming'), ('outgoing', 'Outgoing')],
        string='Transfer Type',
        default='incoming',
        required=True,
        tracking=True,
    )
    status = fields.Selection(
        [
            ('requested', 'Requested'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Transfer Status',
        default='requested',
        required=True,
        tracking=True,
    )
    transfer_date = fields.Datetime(string='Transfer Date', default=fields.Datetime.now)
    completion_date = fields.Datetime(string='Completion Date')
    api_reference = fields.Char(string='API Reference')
    registrar = fields.Char(string='Registrar', default='Domainrobot / united-domains')
    price = fields.Float(string='Transfer Price')
    currency_id = fields.Many2one('res.currency', string='Currency')
    api_response_code = fields.Char(string='API Response Code', readonly=True)
    api_response_message = fields.Text(string='API Response Message', readonly=True)
    notes = fields.Text(string='Notes')

    def _get_client(self):
        from odoo.addons.odoo_domain_management.services.domainrobot_client import DomainrobotClient
        return DomainrobotClient.from_system_params(self.env)

    def action_sync_from_api(self):
        """Pull transfer data from the provider and store the raw response summary."""
        self.ensure_one()
        client = self._get_client()
        if self.transfer_type == 'incoming':
            result = client.query_transfer_list()
        else:
            result = client.query_foreign_transfer_list()

        self.write({
            'api_response_code': result.get('code', ''),
            'api_response_message': result.get('description', ''),
            'status': self.status if self.status else 'pending',
        })
        self.message_post(body=_('Transfer list synced from Domainrobot.'))
        return True
