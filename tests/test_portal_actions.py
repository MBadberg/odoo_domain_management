# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestDomainPortalActions(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'Portal Customer'})
        self.asset = self.env['domain.asset'].create({
            'name': 'example.de',
            'partner_id': self.partner.id,
            'status': 'active',
        })

    def test_action_renew_success(self):
        calls = {}

        def fake_renew(domain, period='1Y'):
            calls['period'] = period
            return {'code': '200', 'description': 'ok', 'properties': {}}

        fake = type('FakeClient', (), {'renew_domain': fake_renew})()
        with patch(
                'odoo.addons.odoo_domain_management.services.domainrobot_client.DomainrobotClient.from_system_params',
                return_value=fake):
            self.assertTrue(self.asset.action_renew(2))
        self.assertEqual(calls['period'], '2Y')

    def test_transfer_request_success(self):
        transfer = self.env['domain.transfer'].create({
            'name': 'example.com',
            'partner_id': self.partner.id,
            'transfer_type': 'incoming',
            'status': 'requested',
        })
        calls = {}

        def fake_transfer(domain, action='REQUEST', **kw):
            calls['auth'] = kw.get('auth')
            return {'code': '200', 'description': 'ok', 'properties': {}}

        fake = type('FakeClient', (), {
            'check_domain_transfer': lambda self, domain: {'code': '218', 'description': 'ok', 'properties': {}},
            'transfer_domain': fake_transfer,
        })()
        with patch(
                'odoo.addons.odoo_domain_management.services.domainrobot_client.DomainrobotClient.from_system_params',
                return_value=fake):
            self.assertTrue(transfer.action_request_transfer('SECRET'))
        self.assertEqual(transfer.status, 'pending')
        self.assertEqual(calls['auth'], 'SECRET')

    def test_register_after_payment(self):
        product = self.env['product.product'].create({
            'name': 'Domain (de)',
            'type': 'service',
            'list_price': 12.0,
        })
        self.env['domain.tld'].create({
            'name': 'de',
            'register_price': 12.0,
            'renew_price': 12.0,
            'transfer_price': 10.0,
            'currency_id': self.env.company.currency_id.id,
            'product_id': product.id,
        })
        partner = self.env['res.partner'].create({'name': 'Buyer'})
        order = self.env['sale.order'].create({'partner_id': partner.id})
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': 12.0,
            'domain_name': 'example.de',
            'domain_operation': 'register',
        })
        order._create_domain_orders()
        domain_order = self.env['domain.order'].search([('sale_order_id', '=', order.id)])
        domain_order.write({'owner_contact': 'HANDLE1'})

        calls = {}

        def fake_check(domain):
            calls['check'] = domain
            return {'code': '210', 'description': 'available', 'properties': {}}

        def fake_register(**kw):
            calls['domain'] = kw.get('domain')
            return {'code': '200', 'description': 'ok',
                    'properties': {'DOMAINID': ['123'], 'EXTERNAL_ORDER_ID': ['999']}}

        fake = type('FakeClient', (), {
            'check_domain': fake_check,
            'register_domain': fake_register,
        })()
        with patch(
                'odoo.addons.odoo_domain_management.services.domainrobot_client.DomainrobotClient.from_system_params',
                return_value=fake):
            order._register_domains_after_payment()

        self.assertEqual(domain_order.state, 'registered')
        self.assertEqual(calls['domain'], 'example.de')

    def test_add_domain_line_to_cart(self):
        """Regression: adding a domain to the cart must not fail with 500.

        ``_add_domain_line`` previously called ``_get_display_price`` on
        ``sale.order``, which raised ``AttributeError`` (the method belongs to
        ``sale.order.line``). The price must now be computed via the pricelist.
        """
        product = self.env['product.product'].create({
            'name': 'Domain (de)',
            'type': 'service',
            'list_price': 12.0,
        })
        partner = self.env['res.partner'].create({'name': 'Buyer'})
        order = self.env['sale.order'].create({'partner_id': partner.id})

        # No explicit price: computed through the pricelist.
        line = order._add_domain_line(product, 'example.de', 'register')
        self.assertTrue(line)
        self.assertEqual(line.domain_name, 'example.de')
        self.assertEqual(line.domain_operation, 'register')
        self.assertAlmostEqual(line.price_unit, 12.0)

        # Explicit price is respected and a different domain is not merged.
        line2 = order._add_domain_line(product, 'example.com', 'register', price_unit=20.0)
        self.assertAlmostEqual(line2.price_unit, 20.0)
        self.assertEqual(len(order.order_line), 2)
