# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    domain_order_ids = fields.One2many(
        'domain.order', 'sale_order_id', string='Domain Orders')

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            order._create_domain_orders()
        return res

    def _create_domain_orders(self):
        """Create pending ``domain.order`` records for every domain line.

        Registration against the Domainrobot API is intentionally NOT triggered
        here: it happens after payment (Phase 4) or manually from the backend.
        """
        self.ensure_one()
        DomainOrder = self.env['domain.order']
        for line in self.order_line:
            if line.domain_operation != 'register':
                continue
            domain_name = (line.domain_name or '').strip().lower()
            if not domain_name:
                continue
            if DomainOrder.search(
                    [('sale_order_id', '=', self.id), ('name', '=', domain_name)],
                    limit=1):
                continue
            tld = self.env['domain.tld']._get_for_domain(domain_name)
            product = tld.product_id or line.product_id
            DomainOrder.create({
                'name': domain_name,
                'partner_id': self.partner_id.id,
                'user_id': self.user_id.id,
                'sale_order_id': self.id,
                'product_id': product.id,
                'price_unit': line.price_unit,
                'currency_id': self.currency_id.id,
                'period': 1,
                'state': 'draft',
            })


    def _add_domain_line(self, product, domain_name, operation='register', price_unit=None):
        """Add a cart line for one domain (never merged with other domains)."""
        self.ensure_one()
        domain_name = (domain_name or '').strip().lower()
        if not product:
            raise UserError(_('No product configured for this domain extension.'))
        existing = self.order_line.filtered(
            lambda line: line.product_id.id == product.id
            and (line.domain_name or '').strip().lower() == domain_name
            and line.domain_operation == operation)
        if existing:
            existing[0].product_uom_qty += 1
            return existing[0]
        taxes = product.taxes_id.filtered(
            lambda tax: tax.company_id in (False, self.company_id))
        vals = {
            'order_id': self.id,
            'product_id': product.id,
            'name': domain_name,
            'product_uom_qty': 1.0,
            'product_uom_id': product.uom_id.id,
            'tax_ids': [(6, 0, taxes.ids)],
            'domain_name': domain_name,
            'domain_operation': operation,
        }
        # When no explicit price is given, leave ``price_unit`` unset so Odoo
        # computes it through the standard sale.order.line flow (pricelist).
        if price_unit is not None:
            vals['price_unit'] = price_unit
        return self.env['sale.order.line'].sudo().create(vals)

    def _register_domains_after_payment(self):
        """Register/renew domains once the sale order has been paid."""
        for order in self:
            order._create_domain_orders()
            for domain_order in order.domain_order_ids.filtered(
                    lambda d: d.state not in ('registered', 'cancelled')):
                domain_order._try_auto_register()
            for line in order.order_line.filtered(
                    lambda l: l.domain_operation == 'renew' and l.domain_name):
                order._process_renewal_line(line)
        return True

    def _process_renewal_line(self, line):
        """Renew the domain referenced by a paid renewal line."""
        asset = self.env['domain.asset'].search(
            [('name', '=', (line.domain_name or '').strip().lower())], limit=1)
        if not asset:
            return False
        try:
            asset.action_renew(int(line.product_uom_qty or 1))
            return True
        except Exception as exc:  # pylint: disable=broad-except
            _logger.warning('Renewal via shop failed for %s: %s', asset.name, exc)
            asset.message_post(body=_('Renewal via shop failed: %s') % exc)
            return False


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    domain_name = fields.Char(
        string='Domain Name',
        index=True,
        copy=False,
        help='Fully qualified domain name sold on this line.',
    )
    domain_operation = fields.Selection(
        [('register', 'Register'), ('renew', 'Renew'), ('transfer', 'Transfer')],
        string='Domain Operation',
        default='register',
        copy=False,
    )
