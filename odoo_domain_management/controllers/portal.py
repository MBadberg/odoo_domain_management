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

    # ── Portal home count ─────────────────────────────────────────────────────

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'domain_count' in counters:
            partner = request.env.user.partner_id
            values['domain_count'] = request.env['domain.asset'].search_count(
                [('partner_id', '=', partner.id)]
            )
        return values

    # ── My Domains list ───────────────────────────────────────────────────────

    @http.route('/my/domains', type='http', auth='user', website=True)
    def portal_my_domains(self, page=1, **kw):
        """List all managed domains belonging to the logged-in user."""
        partner = request.env.user.partner_id
        DomainAsset = request.env['domain.asset']

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
            {'domain': domain, 'page_name': 'domain'},
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
                        error = f"API error {api_result.get('code')}: {api_result.get('description')}"
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

        if not domain_name:
            error = _('No domain name provided.')
        else:
            try:
                partner = request.env.user.partner_id
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

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_domain_asset_or_raise(self, domain_id):
        """Return a domain.asset record, enforcing ownership."""
        DomainAsset = request.env['domain.asset']
        try:
            domain = DomainAsset.browse(domain_id)
            if not domain.exists():
                raise MissingError(_('This domain does not exist.'))
            # Enforce that the current user owns the domain
            if domain.partner_id != request.env.user.partner_id:
                raise AccessError(_('You do not have access to this domain.'))
            return domain
        except (AccessError, MissingError):
            raise
        except Exception as exc:
            raise MissingError(_('Domain not found.')) from exc
