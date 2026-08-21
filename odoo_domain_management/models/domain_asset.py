# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class DomainAsset(models.Model):
    """Represents a successfully registered / managed domain belonging to a customer."""

    _name = 'domain.asset'
    _description = 'Managed Domain'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # ── Basic fields ─────────────────────────────────────────────────────────

    name = fields.Char(
        string='Domain Name',
        required=True,
        tracking=True,
        help='Fully qualified domain name, e.g. example.de',
    )
    tld = fields.Char(
        string='TLD',
        compute='_compute_tld',
        store=True,
    )

    # ── Ownership ─────────────────────────────────────────────────────────────

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=False,
        ondelete='restrict',
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Portal User',
        ondelete='set null',
    )

    # ── External identifiers ──────────────────────────────────────────────────

    external_domain_id = fields.Char(
        string='External Domain ID',
        readonly=True,
        index=True,
        help='Domain ID / reference returned by the Domainrobot API.',
    )
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
    registrar = fields.Char(
        string='Registrar / Provider',
        default='united-domains Reselling',
    )

    # ── Dates ─────────────────────────────────────────────────────────────────

    date_registration = fields.Date(string='Registration Date')
    date_expiry = fields.Date(string='Expiry Date', tracking=True)

    # ── Status ────────────────────────────────────────────────────────────────

    status = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('pending_transfer', 'Pending Transfer'),
            ('cancelled', 'Cancelled'),
            ('unknown', 'Unknown'),
        ],
        default='unknown',
        required=True,
        tracking=True,
        string='Status',
    )

    # ── Nameservers ───────────────────────────────────────────────────────────

    nameserver0 = fields.Char(string='Nameserver 1')
    nameserver1 = fields.Char(string='Nameserver 2')
    nameserver2 = fields.Char(string='Nameserver 3')

    # ── Linked order ──────────────────────────────────────────────────────────

    order_id = fields.Many2one(
        'domain.order',
        string='Origin Order',
        ondelete='set null',
    )

    # ── Notes ─────────────────────────────────────────────────────────────────

    notes = fields.Text(string='Notes')

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('name')
    def _compute_tld(self):
        for rec in self:
            if rec.name and '.' in rec.name:
                rec.tld = rec.name.rsplit('.', 1)[-1]
            else:
                rec.tld = False

    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_days_until_expiry',
        store=True,
    )

    @api.depends('date_expiry')
    def _compute_days_until_expiry(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_expiry:
                delta = rec.date_expiry - today
                rec.days_until_expiry = delta.days
            else:
                rec.days_until_expiry = 0

    # ── Business methods ──────────────────────────────────────────────────────

    def action_sync_status(self):
        """Sync domain details from the Domainrobot API."""
        self.ensure_one()
        if self.env.context.get('skip_domainrobot_sync'):
            return False
        try:
            from odoo.addons.odoo_domain_management.services.domainrobot_sync import DomainrobotSyncService
            DomainrobotSyncService(self.env).sync_domain_record(self)
            self.message_post(body=_('Status synced from Domainrobot.'))
            return True
        except Exception as exc:  # pragma: no cover - defensive guard
            _logger.warning('Domain asset sync failed for %s: %s', self.name, exc)
            self.with_context(skip_domainrobot_sync=True).write({
                'sync_state': 'error',
                'sync_error': str(exc),
                'needs_sync': True,
            })
            self.message_post(body=_('Domainrobot sync failed: %s') % exc)
            return False

    def action_sync_domainrobot(self):
        return self.action_sync_status()

    def _get_client(self):
        from odoo.addons.odoo_domain_management.services.domainrobot_client import DomainrobotClient
        return DomainrobotClient.from_system_params(self.env)
