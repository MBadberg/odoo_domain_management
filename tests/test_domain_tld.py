# -*- coding: utf-8 -*-
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestDomainTld(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.currency = self.env.company.currency_id
        self.tld_de = self.env['domain.tld'].create({
            'name': 'de',
            'register_price': 12.0,
            'renew_price': 12.0,
            'transfer_price': 10.0,
            'currency_id': self.currency.id,
        })

    def test_tld_from_domain(self):
        self.assertEqual(self.env['domain.tld']._tld_from_domain('example.de'), 'de')
        self.assertEqual(self.env['domain.tld']._tld_from_domain('EXAMPLE.COM'), 'com')
        self.assertFalse(self.env['domain.tld']._tld_from_domain('nodomain'))

    def test_get_for_domain(self):
        self.assertEqual(self.env['domain.tld']._get_for_domain('example.de'), self.tld_de)
        self.assertFalse(self.env['domain.tld']._get_for_domain('example.xyz'))

    def test_create_domain_order_from_sale_line(self):
        product = self.env['product.product'].create({
            'name': 'Domain (de)',
            'type': 'service',
            'list_price': 12.0,
        })
        self.tld_de.product_id = product.id
        partner = self.env['res.partner'].create({'name': 'Test Customer'})
        order = self.env['sale.order'].create({'partner_id': partner.id})
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': 12.0,
            'domain_name': 'example.de',
        })

        order._create_domain_orders()

        domain_order = self.env['domain.order'].search([('sale_order_id', '=', order.id)])
        self.assertEqual(len(domain_order), 1)
        self.assertEqual(domain_order.name, 'example.de')
        self.assertEqual(domain_order.partner_id, partner)
        self.assertEqual(domain_order.product_id, product)

    def test_parse_price_relations(self):
        from odoo.addons.odoo_domain_management.services.domainrobot_sync import DomainrobotSyncService
        service = DomainrobotSyncService(self.env)
        result = {
            'code': '200',
            'properties': {
                'RELATION TYPE': [
                    'PRICE_CLASS_DOMAIN_DE_ANNUAL',
                    'PRICE_CLASS_DOMAIN_DE_CURRENCY',
                    'PRICE_CLASS_DOMAIN_DE_SETUP',
                    'PRICE_CLASS_DOMAIN_DE_TRANSFER',
                ],
                'RELATION VALUE': ['6.00', 'EUR', '3.00', '6.00'],
            },
        }
        parsed = service._parse_price_relations(result)
        self.assertEqual(parsed['de']['annual'], 6.0)
        self.assertEqual(parsed['de']['setup'], 3.0)
        self.assertEqual(parsed['de']['transfer'], 6.0)
        self.assertEqual(parsed['de']['currency'], 'EUR')

    def test_compute_sell_price(self):
        self.tld_de.markup_percent = 20.0
        self.assertEqual(self.tld_de._compute_sell_price(10.0), 12.0)
        self.assertEqual(self.tld_de._compute_sell_price(0.0), 0.0)

    def test_markup_fallback_global(self):
        self.env['ir.config_parameter'].set_param('domainrobot.markup_percent', '10.0')
        self.assertEqual(self.tld_de._get_markup_percent(), 10.0)
        self.assertEqual(self.tld_de._compute_sell_price(10.0), 11.0)
        # per-TLD override
        self.tld_de.markup_percent = 25.0
        self.assertEqual(self.tld_de._get_markup_percent(), 25.0)
        self.assertEqual(self.tld_de._compute_sell_price(10.0), 12.5)
