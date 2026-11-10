# -*- coding: utf-8 -*-
"""Public website controllers: AJAX search, pricing and add-to-cart.

The ``/domains`` landing page itself is a real ``website.page`` record (see
``views/website_domain_templates.xml``) and is therefore served by the website
engine: it appears under Website → Pages, can be (un)published and its blocks
are editable in the website builder. This controller only exposes the small
endpoints that feed the dynamic blocks on that page.
"""
import logging

from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError

from odoo.addons.odoo_domain_management.services.domainrobot_client import (
    DomainrobotAPIError,
    DomainrobotClient,
)

_logger = logging.getLogger(__name__)


class DomainWebsiteController(http.Controller):

    def _active_tlds(self):
        return request.env['domain.tld'].sudo().search(
            [('active', '=', True)], order='sequence, name')

    @http.route('/domains/search', type='http', auth='public', website=True,
                methods=['POST'], csrf=False)
    def domain_search(self, domain_name='', **kw):
        domain_name = (domain_name or '').strip().lower()
        results = []
        error = None
        tlds = self._active_tlds()

        if not domain_name:
            error = _('Bitte gib einen Domainnamen ein.')
        elif not tlds:
            error = _('Es sind noch keine Domain-Endungen konfiguriert.')
        else:
            base = domain_name.split('.')[0]
            names = [f'{base}.{t.name}' for t in tlds]
            try:
                client = DomainrobotClient.from_system_params(request.env)
                api_result = client.check_domains(names)
                if api_result.get('code') == '200':
                    domaincheck = api_result.get('properties', {}).get('DOMAINCHECK', [])
                    for i, tld in enumerate(tlds):
                        status = domaincheck[i] if i < len(domaincheck) else ''
                        results.append({
                            'domain': names[i],
                            'tld': tld,
                            'available': str(status).startswith('210'),
                        })
                else:
                    error = _('API-Fehler %s: %s') % (
                        api_result.get('code'), api_result.get('description'))
            except DomainrobotAPIError as exc:
                _logger.warning('Domain search failed: %s', exc)
                error = str(exc)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.error('Unexpected error during domain search: %s', exc)
                error = _('Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es später erneut.')

        return request.render('odoo_domain_management.domain_search_results', {
            'results': results,
            'error': error,
        })

    @http.route('/domains/pricing', type='http', auth='public', website=True)
    def domain_pricing(self, **kw):
        return request.render('odoo_domain_management.domain_pricing_results', {
            'tlds': self._active_tlds(),
        })

    @http.route('/domain/cart/add', type='http', auth='public', website=True, methods=['POST'])
    def domain_cart_add(self, domain_name='', **kw):
        domain_name = (domain_name or '').strip().lower()
        if not domain_name:
            raise UserError(_('Kein Domainname angegeben.'))

        tld = request.env['domain.tld'].sudo()._get_for_domain(domain_name)
        product = tld.product_id
        if not product:
            raise UserError(_('Diese Domain-Endung ist noch nicht kaufbar.'))

        order = request.website._get_and_cache_current_cart()
        if not order:
            order = request.website._create_cart()
        order._add_domain_line(product, domain_name, 'register')
        return request.redirect('/shop/cart')
