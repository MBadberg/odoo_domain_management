# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DomainPriceList(models.Model):
    """A Domainrobot price list (UserClass) assigned to customers.

    Domainrobot groups prices into *UserClasses*; each UserClass holds its own
    ``PRICE_CLASS_DOMAIN_<tld>_<type>`` relations. This model mirrors one such
    class so its prices can be synced and assigned per customer.
    """

    _name = 'domain.price.list'
    _description = 'Domain Price List'
    _order = 'sequence, name'
    _name_uniq = models.Constraint(
        'unique (name)', 'A price list already exists with this name.')

    name = fields.Char(string='Price List', required=True)
    external_userclass = fields.Char(
        string='Domainrobot UserClass',
        copy=False,
        index=True,
        help='Name of the UserClass in Domainrobot that holds these prices.',
    )
    is_default = fields.Boolean(
        string='Default',
        default=False,
        help='Used when a customer has no price list assigned.',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    price_line_ids = fields.One2many(
        'domain.price.line', 'price_list_id', string='Prices')
    notes = fields.Text(string='Notes')

    def action_sync_prices(self):
        """Sync this price list's per-TLD prices from Domainrobot."""
        from odoo.addons.odoo_domain_management.services.domainrobot_sync import DomainrobotSyncService
        service = DomainrobotSyncService(self.env)
        count = 0
        for price_list in self:
            count += len(service._sync_price_list_prices(price_list))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Price list sync',
                'message': '%d price(s) synced.' % count,
                'type': 'success' if count else 'warning',
                'sticky': False,
            },
        }


class DomainPriceLine(models.Model):
    """Per-TLD prices of one price list."""

    _name = 'domain.price.line'
    _description = 'Domain Price Line'
    _order = 'tld'
    _name_uniq = models.Constraint(
        'unique (price_list_id, tld)',
        'A price already exists for this TLD in this price list.',
    )

    price_list_id = fields.Many2one(
        'domain.price.list', string='Price List',
        required=True, ondelete='cascade', index=True)
    tld = fields.Char(string='TLD', required=True)
    register_price = fields.Monetary(
        string='Registration Price', currency_field='currency_id')
    renew_price = fields.Monetary(
        string='Renewal Price', currency_field='currency_id')
    transfer_price = fields.Monetary(
        string='Transfer Price', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)

    @api.model
    def _get_for(self, price_list, tld):
        """Return the price line of *price_list* for *tld*, if any."""
        tld = (tld or '').strip().lower()
        if not price_list or not tld:
            return self.browse()
        return self.search([
            ('price_list_id', '=', price_list.id),
            ('tld', '=', tld),
        ], limit=1)
