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
    external_transfer_id = fields.Char(string='External Transfer ID', index=True, copy=False)
    last_sync_at = fields.Datetime(string='Last Sync', readonly=True, index=True)
    sync_state = fields.Selection(
        [('draft', 'Draft'), ('synced', 'Synced'), ('error', 'Error')],
        default='draft',
        readonly=True,
        index=True,
        string='Sync State',
    )
    sync_error = fields.Text(string='Sync Error', readonly=True)
    needs_sync = fields.Boolean(string='Needs Sync', default=False, index=True)
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
        if self.env.context.get('skip_domainrobot_sync'):
            return False
        try:
            from odoo.addons.odoo_domain_management.services.domainrobot_sync import DomainrobotSyncService
            DomainrobotSyncService(self.env).sync_transfer_record(self)
            self.message_post(body=_('Transfer list synced from Domainrobot.'))
            return True
        except Exception as exc:  # pragma: no cover - defensive guard
            self.with_context(skip_domainrobot_sync=True).write({
                'sync_state': 'error',
                'sync_error': str(exc),
                'needs_sync': True,
            })
            self.message_post(body=_('Domainrobot transfer sync failed: %s') % exc)
            return False

    def action_sync_domainrobot(self):
        return self.action_sync_from_api()
