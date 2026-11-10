# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestDomainPriceList(common.TransactionCase):

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
        self.price_list = self.env['domain.price.list'].create({
            'name': 'VIP',
            'external_userclass': 'vip',
        })

    def test_effective_prices_fallback(self):
        """Without a price list the TLD's own prices apply."""
        partner = self.env['res.partner'].create({'name': 'Customer'})
        self.assertEqual(self.tld_de._effective_prices(partner), (12.0, 12.0, 10.0))

    def test_effective_prices_from_list(self):
        """A customer with a price list gets that list's prices."""
        self.env['domain.price.line'].create({
            'price_list_id': self.price_list.id,
            'tld': 'de',
            'register_price': 8.0,
            'renew_price': 8.0,
            'transfer_price': 7.0,
            'currency_id': self.currency.id,
        })
        partner = self.env['res.partner'].create({
            'name': 'VIP Customer',
            'domain_price_list_id': self.price_list.id,
        })
        self.assertEqual(self.tld_de._effective_prices(partner), (8.0, 8.0, 7.0))

    def test_sell_price_for_partner(self):
        """The sell price applies the markup on the customer's cost."""
        self.env['domain.price.line'].create({
            'price_list_id': self.price_list.id,
            'tld': 'de',
            'register_price': 8.0,
            'renew_price': 8.0,
            'transfer_price': 7.0,
            'currency_id': self.currency.id,
        })
        self.env['ir.config_parameter'].set_param('domainrobot.markup_percent', '25.0')
        partner = self.env['res.partner'].create({
            'name': 'VIP Customer',
            'domain_price_list_id': self.price_list.id,
        })
        self.assertAlmostEqual(self.tld_de._sell_price_for_partner(partner), 10.0)

    def test_sync_price_lists(self):
        from odoo.addons.odoo_domain_management.services.domainrobot_sync import DomainrobotSyncService
        userclass_result = {
            'code': '200',
            'properties': {'USERCLASS': ['standard', 'vip']},
        }
        fake = type('FakeClient', (), {'query_user_class_list': lambda self: userclass_result})()
        with patch(
                'odoo.addons.odoo_domain_management.services.domainrobot_client.DomainrobotClient.from_system_params',
                return_value=fake):
            service = DomainrobotSyncService(self.env)
            synced = service.sync_price_lists()

        self.assertEqual(sorted(rec.external_userclass for rec in synced), ['standard', 'vip'])

    def test_sync_price_list_prices(self):
        from odoo.addons.odoo_domain_management.services.domainrobot_sync import DomainrobotSyncService
        userclass_result = {
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
        fake = type('FakeClient', (), {'status_userclass': lambda self, userclass: userclass_result})()
        with patch(
                'odoo.addons.odoo_domain_management.services.domainrobot_client.DomainrobotClient.from_system_params',
                return_value=fake):
            service = DomainrobotSyncService(self.env)
            service._sync_price_list_prices(self.price_list)

        line = self.env['domain.price.line'].search([
            ('price_list_id', '=', self.price_list.id),
            ('tld', '=', 'de'),
        ])
        self.assertTrue(line)
        self.assertAlmostEqual(line.register_price, 9.0)
