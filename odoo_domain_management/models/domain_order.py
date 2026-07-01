# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DomainOrder(models.Model):
    """Represents a domain registration order initiated by a customer."""

    _name = 'domain.order'
    _description = 'Domain Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

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
        help='Top-level domain extracted from the domain name.',
    )
    period = fields.Integer(
        string='Registration Period (years)',
        default=1,
        required=True,
    )

    # ── Ownership ─────────────────────────────────────────────────────────────

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Portal User',
        ondelete='set null',
    )

    # ── Status ────────────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('availability_checked', 'Availability Checked'),
            ('pending', 'Purchase Pending'),
            ('registered', 'Registered'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        required=True,
        tracking=True,
        string='Status',
    )
    availability = fields.Selection(
        selection=[
            ('unknown', 'Unknown'),
            ('available', 'Available'),
            ('unavailable', 'Unavailable'),
        ],
        default='unknown',
        string='Availability',
    )

    # ── External / API fields ─────────────────────────────────────────────────

    external_order_id = fields.Char(
        string='External Order ID',
        readonly=True,
        help='Transaction / order ID returned by the Domainrobot API.',
    )
    api_response_code = fields.Char(
        string='API Response Code',
        readonly=True,
    )
    api_response_message = fields.Text(
        string='API Response Message',
        readonly=True,
    )

    # ── Nameservers (required for domain registration) ────────────────────────

    nameserver0 = fields.Char(string='Nameserver 1', default='ns1a.dodns.net')
    nameserver1 = fields.Char(string='Nameserver 2', default='ns2a.dodns.net')

    # ── Contact handles (Domainrobot-specific) ────────────────────────────────

    owner_contact = fields.Char(
        string='Owner Contact Handle',
        help='Contact handle returned by addcontact API call.',
    )
    admin_contact = fields.Char(string='Admin Contact Handle')
    tech_contact = fields.Char(string='Tech Contact Handle')
    billing_contact = fields.Char(string='Billing Contact Handle')

    # ── Linked asset ──────────────────────────────────────────────────────────

    asset_id = fields.Many2one(
        'domain.asset',
        string='Managed Domain',
        readonly=True,
    )

    # ── Timestamps ───────────────────────────────────────────────────────────

    date_order = fields.Datetime(string='Order Date', default=fields.Datetime.now)
    date_registered = fields.Datetime(string='Registration Date', readonly=True)

    # ── Computed fields ───────────────────────────────────────────────────────

    @api.depends('name')
    def _compute_tld(self):
        for rec in self:
            if rec.name and '.' in rec.name:
                rec.tld = rec.name.rsplit('.', 1)[-1]
            else:
                rec.tld = False

    # ── Display name ──────────────────────────────────────────────────────────

    def _rec_name_fallback(self):
        return self.name or _('New Domain Order')

    # ── Business methods ──────────────────────────────────────────────────────

    def action_check_availability(self):
        """Call the Domainrobot API to check whether *self.name* is available."""
        self.ensure_one()
        if not self.name:
            raise UserError(_('Please enter a domain name first.'))

        client = self._get_client()
        result = client.check_domain(self.name)

        code = result.get('code')
        description = result.get('description', '')

        self.write({
            'api_response_code': code,
            'api_response_message': description,
        })

        if code == '210':
            self.write({'availability': 'available', 'state': 'availability_checked'})
        elif code == '211':
            self.write({'availability': 'unavailable', 'state': 'availability_checked'})
        else:
            self.write({'availability': 'unknown'})
            raise UserError(_('API error %s: %s') % (code, description))

        return True

    def action_purchase(self):
        """Trigger domain registration via the Domainrobot API."""
        self.ensure_one()
        if self.availability != 'available':
            raise UserError(
                _('Domain "%s" must be confirmed available before purchasing.') % self.name
            )
        if not (self.nameserver0 and self.nameserver1):
            raise UserError(_('At least two nameservers are required for registration.'))
        if not self.owner_contact:
            raise UserError(
                _('An owner contact handle is required. '
                  'Please create one first via the API or set it manually.')
            )

        client = self._get_client()
        result = client.register_domain(
            domain=self.name,
            period=self.period,
            nameserver0=self.nameserver0,
            nameserver1=self.nameserver1,
            owner_contact=self.owner_contact,
            admin_contact=self.admin_contact or self.owner_contact,
            tech_contact=self.tech_contact or self.owner_contact,
            billing_contact=self.billing_contact or self.owner_contact,
        )

        code = result.get('code')
        description = result.get('description', '')
        self.write({
            'api_response_code': code,
            'api_response_message': description,
        })

        if code == '200':
            now = fields.Datetime.now()
            self.write({
                'state': 'registered',
                'date_registered': now,
                'external_order_id': result.get('external_id', ''),
            })
            # Create or update the linked domain asset
            self._create_or_update_asset()
            self.message_post(body=_('Domain successfully registered via Domainrobot API.'))
        else:
            self.write({'state': 'failed'})
            raise UserError(_('Domain registration failed – API code %s: %s') % (code, description))

        return True

    def action_sync_status(self):
        """Sync the domain status from the API (skeleton – extend as needed)."""
        self.ensure_one()
        # TODO: call statusDomain API command when available in your account
        # client = self._get_client()
        # result = client.status_domain(self.name)
        _logger.info('action_sync_status called for domain.order %s – not yet implemented', self.name)
        self.message_post(body=_('Status sync: not yet implemented for this domain.'))

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_client(self):
        """Return a configured DomainrobotClient instance."""
        from odoo.addons.odoo_domain_management.services.domainrobot_client import DomainrobotClient
        return DomainrobotClient.from_system_params(self.env)

    def _create_or_update_asset(self):
        """Create or update a domain.asset record after successful registration."""
        DomainAsset = self.env['domain.asset']
        asset = DomainAsset.search([('name', '=', self.name)], limit=1)
        vals = {
            'name': self.name,
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'status': 'active',
            'order_id': self.id,
        }
        if asset:
            asset.write(vals)
        else:
            asset = DomainAsset.create(vals)
        self.asset_id = asset
