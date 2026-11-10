# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class DomainTld(models.Model):
    """Maps a TLD to its shop product variant and base prices.

    Option A: a single generic "Domain" product has one variant per TLD; this
    record links the TLD to its variant and holds the Domainrobot base prices.
    Odoo pricelists then govern the actual sale price.
    """

    _name = 'domain.tld'
    _description = 'Domain TLD'
    _order = 'sequence, name'
    _name_uniq = models.Constraint(
        'unique (name)',
        'A TLD entry already exists for this extension.',
    )

    DEFAULT_TLDS = [
        # name, registration price, renewal price, transfer price
        ('de', 12.90, 12.90, 10.90),
        ('com', 14.90, 15.90, 12.90),
        ('net', 16.90, 17.90, 14.90),
        ('org', 15.90, 16.90, 13.90),
        ('info', 8.90, 9.90, 7.90),
        ('biz', 11.90, 12.90, 9.90),
    ]

    name = fields.Char(string='TLD', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    product_id = fields.Many2one(
        'product.product',
        string='Product Variant',
        ondelete='set null',
        index=True,
        help='Website product variant used to sell this TLD.',
    )

    register_price = fields.Monetary(string='Registration Price', currency_field='currency_id')
    renew_price = fields.Monetary(string='Renewal Price', currency_field='currency_id')
    transfer_price = fields.Monetary(string='Transfer Price', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    markup_percent = fields.Float(
        string='Markup (%)',
        default=0.0,
        help='Markup applied on the Domainrobot cost to compute the sale price. '
             '0 means the global default from Settings is used.',
    )

    registrar = fields.Char(string='Registrar', default='united-domains Reselling')
    notes = fields.Text(string='Notes')

    @staticmethod
    def _tld_from_domain(domain_name):
        """Return the TLD of *domain_name* (e.g. ``example.de`` -> ``de``)."""
        if not domain_name or '.' not in domain_name:
            return False
        return domain_name.strip().lower().rsplit('.', 1)[-1]

    @api.model
    def _get_for_domain(self, domain_name):
        """Return the active ``domain.tld`` record matching *domain_name*."""
        tld = self._tld_from_domain(domain_name)
        if not tld:
            return self.browse()
        return self.search([('name', '=', tld), ('active', '=', True)], limit=1)

    @api.model
    def _get_product_for_domain(self, domain_name):
        """Return the shop product variant for *domain_name*."""
        return self._get_for_domain(domain_name).product_id

    @api.model
    def _seed_default_tlds(self):
        """Create missing TLDs, attribute values and product variants.

        Idempotent and non-destructive: existing records (and their prices)
        are left untouched, so it is safe to run on every install/upgrade.
        """
        category = self.env['product.category'].search([('name', '=', 'Domains')], limit=1)
        if not category:
            category = self.env['product.category'].create({'name': 'Domains'})

        attribute = self.env['product.attribute'].search([('name', '=', 'TLD')], limit=1)
        if not attribute:
            attribute = self.env['product.attribute'].create({
                'name': 'TLD',
                'create_variant': 'always',
                'display_type': 'select',
            })

        template = self.env['product.template'].search([
            ('name', '=', 'Domain'),
            ('categ_id', '=', category.id),
        ], limit=1)
        if not template:
            template = self.env['product.template'].create({
                'name': 'Domain',
                'type': 'service',
                'categ_id': category.id,
                'list_price': 0.0,
                'sale_ok': True,
                'is_published': True,
                'description': 'Domain registration via Domainrobot (united-domains Reselling)',
            })

        company_currency = self.env.company.currency_id

        value_ids = []
        for tld, register, renew, transfer in self.DEFAULT_TLDS:
            value = self.env['product.attribute.value'].search([
                ('attribute_id', '=', attribute.id),
                ('name', '=', tld),
            ], limit=1)
            if not value:
                value = self.env['product.attribute.value'].create({
                    'attribute_id': attribute.id,
                    'name': tld,
                    'default_extra_price': register,
                })
            value_ids.append(value.id)

            rec = self.search([('name', '=', tld)], limit=1)
            if not rec:
                self.create({
                    'name': tld,
                    'register_price': register,
                    'renew_price': renew,
                    'transfer_price': transfer,
                    'currency_id': company_currency.id,
                })

        line = self.env['product.template.attribute.line'].search([
            ('product_tmpl_id', '=', template.id),
            ('attribute_id', '=', attribute.id),
        ], limit=1)
        if not line:
            line = self.env['product.template.attribute.line'].create({
                'product_tmpl_id': template.id,
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, value_ids)],
            })
        else:
            missing = [v for v in value_ids if v not in line.value_ids.ids]
            if missing:
                line.write({'value_ids': [(4, v) for v in missing]})

        for tld, _register, _renew, _transfer in self.DEFAULT_TLDS:
            value = self.env['product.attribute.value'].search([
                ('attribute_id', '=', attribute.id),
                ('name', '=', tld),
            ], limit=1)
            variant = self.env['product.product'].search([
                ('product_tmpl_id', '=', template.id),
                ('product_template_attribute_value_ids.product_attribute_value_id', '=', value.id),
            ], limit=1)
            rec = self.search([('name', '=', tld)], limit=1)
            if rec and variant and not rec.product_id:
                rec.product_id = variant.id

        return True

    def action_seed_tlds(self):
        """Button action: (re)seed TLDs, attribute values and product variants."""
        self._seed_default_tlds()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('TLD products'),
                'message': _('TLD products seeded successfully.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def _get_markup_percent(self):
        """Return this TLD's markup, falling back to the global default."""
        self.ensure_one()
        if self.markup_percent:
            return self.markup_percent
        icp = self.env['ir.config_parameter'].sudo()
        return float(icp.get_param('domainrobot.markup_percent', '0.0') or 0.0)

    def _compute_sell_price(self, cost):
        """Return *cost* + markup as the sale price (rounded to 2 decimals)."""
        self.ensure_one()
        return round((cost or 0.0) * (1.0 + self._get_markup_percent() / 100.0), 2)

    def _set_product_price(self, price):
        """Write *price* onto the linked product variant's TLD attribute value."""
        product = self.product_id
        if not product:
            return False
        ptav = product.product_template_attribute_value_ids.filtered(
            lambda v: v.product_attribute_value_id.attribute_id.name == 'TLD')
        if ptav:
            ptav[0].write({'price_extra': price})
            return True
        return False

    def _apply_markup_to_products(self):
        """Set each TLD's product price to cost × (1 + markup)."""
        applied = 0
        for rec in self:
            if rec._set_product_price(rec._compute_sell_price(rec.register_price)):
                applied += 1
        return applied

    def action_apply_markup_to_products(self):
        """Button: (re)apply the markup to the linked product prices."""
        applied = self._apply_markup_to_products()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Markup applied'),
                'message': _('%d product prices updated.') % applied,
                'type': 'success' if applied else 'warning',
                'sticky': False,
            },
        }

    def _get_client(self):
        from odoo.addons.odoo_domain_management.services.domainrobot_client import DomainrobotClient
        return DomainrobotClient.from_system_params(self.env)

    def action_sync_prices(self):
        """Pull per-TLD costs from Domainrobot, then apply the markup to products."""
        from odoo.addons.odoo_domain_management.services.domainrobot_sync import DomainrobotSyncService
        updated = DomainrobotSyncService(self.env).sync_prices()
        if updated:
            self.env['domain.tld'].browse([rec.id for rec in updated.values()])._apply_markup_to_products()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Price sync'),
                'message': _('%d TLD prices updated and markup applied.') % len(updated),
                'type': 'success' if updated else 'warning',
                'sticky': False,
            },
        }
