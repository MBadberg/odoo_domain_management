# -*- coding: utf-8 -*-
"""
Portal controller for domain management.

Routes:
  GET  /my/domains                  – list all domains owned by the current user
  GET  /my/domains/<int:domain_id>  – domain detail page
  GET  /my/domains/check            – availability check form
  POST /my/domains/check            – execute availability check (AJAX-friendly)
  POST /my/domains/purchase         – create an order and trigger purchase
"""
import logging
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError, UserError

_logger = logging.getLogger(__name__)


class DomainPortalController(CustomerPortal):
    """Extends the Odoo customer portal with domain management pages."""

    def _get_portal_partner(self):
        """Return the current user's partner record if it exists and is valid."""
        user = getattr(request.env, 'user', False)
        if not user:
            return False
        partner = user.partner_id
        return partner if partner and partner.exists() else False

    # ── Portal home count ─────────────────────────────────────────────────────

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'domain_count' in counters:
            partner = self._get_portal_partner()
            values['domain_count'] = (
                request.env['domain.asset'].search_count([('partner_id', '=', partner.id)])
                if partner
                else 0
            )
        return values

    # ── My Domains list ───────────────────────────────────────────────────────

    @http.route('/my/domains', type='http', auth='user', website=True)
    def portal_my_domains(self, page=1, **kw):
        """List all managed domains belonging to the logged-in user."""
        partner = self._get_portal_partner()
        DomainAsset = request.env['domain.asset']

        if not partner or not partner.exists():
            return request.render(
                'odoo_domain_management.portal_my_domains',
                {
                    'domains': DomainAsset.browse(),
                    'pager': portal_pager(url='/my/domains', total=0, page=page, step=20),
                    'page_name': 'domain',
                },
            )

        domain_count = DomainAsset.search_count([('partner_id', '=', partner.id)])
        pager = portal_pager(
            url='/my/domains',
            total=domain_count,
            page=page,
            step=20,
        )
        domains = DomainAsset.search(
            [('partner_id', '=', partner.id)],
            limit=20,
            offset=pager['offset'],
            order='name',
        )

        return request.render(
            'odoo_domain_management.portal_my_domains',
            {
                'domains': domains,
                'pager': pager,
                'page_name': 'domain',
            },
        )

    # ── Domain detail page ────────────────────────────────────────────────────

    @http.route('/my/domains/<int:domain_id>', type='http', auth='user', website=True)
    def portal_domain_detail(self, domain_id, **kw):
        """Show details for one managed domain (owner-only)."""
        domain = self._get_domain_asset_or_raise(domain_id)
        return request.render(
            'odoo_domain_management.portal_domain_detail',
            {
                'domain': domain,
                'page_name': 'domain',
                'renew_error': None,
                'renew_success': None,
            },
        )

    # ── Availability check ────────────────────────────────────────────────────

    @http.route('/my/domains/check', type='http', auth='user', website=True, methods=['GET'])
    def portal_check_form(self, **kw):
        """Render the availability check form."""
        return request.render(
            'odoo_domain_management.portal_check_domain',
            {
                'page_name': 'domain',
                'tlds': ['de', 'com', 'net', 'org', 'info', 'biz'],
            },
        )

    @http.route('/my/domains/check', type='http', auth='user', website=True, methods=['POST'])
    def portal_check_submit(self, domain_name='', tlds=None, **kw):
        """
        Execute a domain availability check.

        If *tlds* is a list (multi-TLD check), calls CheckDomains; otherwise
        calls CheckDomain for the single fully-qualified name.
        """
        results = []
        error = None

        domain_name = (domain_name or '').strip().lower()
        if not domain_name:
            error = _('Please enter a domain name.')
        else:
            try:
                from odoo.addons.odoo_domain_management.services.domainrobot_client import (
                    DomainrobotClient,
                    DomainrobotAPIError,
                )
                client = DomainrobotClient.from_system_params(request.env)

                # Multi-TLD check when a comma-separated list of TLDs is given
                selected_tlds = [t.strip() for t in (tlds or '').split(',') if t.strip()]

                if selected_tlds:
                    # Strip any existing TLD from the input before appending
                    base = domain_name.split('.')[0]
                    domains_to_check = [f'{base}.{t}' for t in selected_tlds]
                    api_result = client.check_domains(domains_to_check)
                    if api_result.get('code') == '200':
                        domaincheck = api_result.get('properties', {}).get('DOMAINCHECK', [])
                        for i, status in enumerate(domaincheck):
                            fqdn = domains_to_check[i] if i < len(domains_to_check) else ''
                            available = status.startswith('210')
                            results.append({
                                'domain': fqdn,
                                'available': available,
                                'status': status,
                            })
                    else:
                        error = _('API error %s: %s') % (api_result.get('code'), api_result.get('description'))
                else:
                    # Single domain check – domain_name may already contain TLD
                    api_result = client.check_domain(domain_name)
                    code = api_result.get('code')
                    results.append({
                        'domain': domain_name,
                        'available': code == '210',
                        'status': f"{code} {api_result.get('description', '')}",
                    })

            except DomainrobotAPIError as exc:
                _logger.warning('Domainrobot API error during check: %s', exc)
                error = str(exc)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.error('Unexpected error during domain check: %s', exc)
                error = _('An unexpected error occurred. Please try again later.')

        return request.render(
            'odoo_domain_management.portal_check_domain',
            {
                'page_name': 'domain',
                'tlds': ['de', 'com', 'net', 'org', 'info', 'biz'],
                'domain_name': domain_name,
                'results': results,
                'error': error,
            },
        )

    # ── Purchase (create order + call API) ────────────────────────────────────

    @http.route('/my/domains/purchase', type='http', auth='user', website=True, methods=['POST'])
    def portal_purchase(self, domain_name='', **kw):
        """
        Create a domain.order for the logged-in user and attempt purchase.

        For the MVP the purchase requires that API credentials are set up and
        the domain was confirmed available. Contact handles must be configured
        by the admin. See TODO notes in the template for how to extend this.
        """
        error = None
        success = None
        domain_name = (domain_name or '').strip().lower()

        partner = self._get_portal_partner()
        if not partner:
            error = _('You must be linked to a partner account before buying a domain.')
        elif not domain_name:
            error = _('No domain name provided.')
        else:
            try:
                # Create a draft order
                order = request.env['domain.order'].sudo().create({
                    'name': domain_name,
                    'partner_id': partner.id,
                    'user_id': request.env.user.id,
                    'state': 'draft',
                })
                # Check availability first, then purchase
                order.action_check_availability()
                if order.availability != 'available':
                    error = _('Domain "%s" is not available for registration.') % domain_name
                    order.sudo().unlink()
                else:
                    # TODO: Prompt the user for contact handle / nameservers
                    # For MVP, admin must pre-configure default values in system params
                    icp = request.env['ir.config_parameter'].sudo()
                    default_contact = icp.get_param('domainrobot.default_contact', '')
                    if default_contact:
                        order.sudo().write({
                            'owner_contact': default_contact,
                            'admin_contact': default_contact,
                            'tech_contact': default_contact,
                            'billing_contact': default_contact,
                        })
                    order.sudo().action_purchase()
                    success = _('Domain "%s" has been successfully registered!') % domain_name

            except UserError as exc:
                error = str(exc)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.error('Unexpected error during domain purchase: %s', exc)
                error = _('An unexpected error occurred. Please contact support.')

        return request.render(
            'odoo_domain_management.portal_purchase_result',
            {
                'page_name': 'domain',
                'domain_name': domain_name,
                'error': error,
                'success': success,
            },
        )

    # ── Contact handle ────────────────────────────────────────────────────────

    @http.route('/my/domains/contact', type='http', auth='user', website=True, methods=['GET'])
    def portal_contact_form(self, **kw):
        """Show the contact-handle status and creation form."""
        partner = self._get_portal_partner()
        return request.render('odoo_domain_management.portal_domain_contact', {
            'page_name': 'domain',
            'partner': partner,
            'message': None,
            'error': None,
        })

    @http.route('/my/domains/contact', type='http', auth='user', website=True, methods=['POST'])
    def portal_contact_submit(self, **kw):
        """Create or update the user's Domainrobot contact handle."""
        partner = self._get_portal_partner()
        message = None
        error = None
        if not partner:
            error = _('You must be linked to a partner account.')
        else:
            try:
                handle = partner._sync_single_contact_handle()
                if handle:
                    message = _('Contact handle created/updated: %s') % handle
                else:
                    error = partner.sync_error or _('Could not create the contact handle.')
            except Exception as exc:  # pylint: disable=broad-except
                _logger.error('Contact handle sync failed: %s', exc)
                error = _('An unexpected error occurred. Please contact support.')
        return request.render('odoo_domain_management.portal_domain_contact', {
            'page_name': 'domain',
            'partner': partner,
            'message': message,
            'error': error,
        })

    # ── Renewal ───────────────────────────────────────────────────────────────

    @http.route('/my/domains/<int:domain_id>/renew', type='http', auth='user', website=True, methods=['POST'])
    def portal_renew_domain(self, domain_id, years=1, **kw):
        """Add a domain renewal to the cart (billed via the shop, renewed after payment)."""
        domain = self._get_domain_asset_or_raise(domain_id)
        tld = request.env['domain.tld'].sudo()._get_for_domain(domain.name)
        product = tld.product_id
        if not product:
            raise UserError(_('Renewal is not available for this domain extension yet.'))
        order = request.website._get_and_cache_current_cart()
        if not order:
            order = request.website._create_cart()
        line = order._add_domain_line(product, domain.name, 'renew')
        line.product_uom_qty = int(years or 1)
        return request.redirect('/shop/cart')

    # ── Transfer ──────────────────────────────────────────────────────────────

    @http.route('/my/domains/transfer', type='http', auth='user', website=True, methods=['GET'])
    def portal_transfer_form(self, **kw):
        """Show the transfer request form and the user's transfer list."""
        partner = self._get_portal_partner()
        transfers = (
            request.env['domain.transfer'].search(
                [('partner_id', '=', partner.id)], order='create_date desc')
            if partner else request.env['domain.transfer'].browse()
        )
        return request.render('odoo_domain_management.portal_domain_transfer', {
            'page_name': 'domain',
            'transfers': transfers,
            'error': None,
            'success': None,
        })

    @http.route('/my/domains/transfer', type='http', auth='user', website=True, methods=['POST'])
    def portal_transfer_submit(self, domain_name='', authcode='', **kw):
        """Request an incoming domain transfer."""
        partner = self._get_portal_partner()
        domain_name = (domain_name or '').strip().lower()
        error = None
        success = None
        if not partner:
            error = _('You must be linked to a partner account.')
        elif not domain_name:
            error = _('Please enter a domain name.')
        else:
            try:
                transfer = request.env['domain.transfer'].sudo().create({
                    'name': domain_name,
                    'partner_id': partner.id,
                    'transfer_type': 'incoming',
                    'status': 'requested',
                })
                transfer.action_request_transfer(authcode)
                success = _('Transfer requested for %s. You will receive a confirmation e-mail.') % domain_name
            except UserError as exc:
                error = str(exc)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.error('Transfer request failed: %s', exc)
                error = _('An unexpected error occurred. Please contact support.')
        transfers = (
            request.env['domain.transfer'].search(
                [('partner_id', '=', partner.id)], order='create_date desc')
            if partner else request.env['domain.transfer'].browse()
        )
        return request.render('odoo_domain_management.portal_domain_transfer', {
            'page_name': 'domain',
            'transfers': transfers,
            'error': error,
            'success': success,
        })

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_domain_asset_or_raise(self, domain_id):
        """Return a domain.asset record, enforcing ownership."""
        DomainAsset = request.env['domain.asset']
        partner = self._get_portal_partner()
        if not partner:
            raise AccessError(_('You are not linked to a partner account.'))
        try:
            domain = DomainAsset.browse(domain_id)
            if not domain.exists():
                raise MissingError(_('This domain does not exist.'))
            # Enforce that the current user owns the domain
            if domain.partner_id != partner:
                raise AccessError(_('You do not have access to this domain.'))
            return domain
        except (AccessError, MissingError):
            raise
        except Exception as exc:
            raise MissingError(_('Domain not found.')) from exc
