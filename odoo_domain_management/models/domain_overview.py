# -*- coding: utf-8 -*-
import logging
from html import escape
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DomainOverview(models.TransientModel):
    """Dashboard with aggregated Domainrobot / Odoo metrics."""

    _name = 'domain.overview'
    _description = 'Domain Overview Dashboard'

    name = fields.Char(default='Overview', readonly=True)
    domain_total = fields.Integer(string='Total Domains', readonly=True)
    domain_active = fields.Integer(string='Active Domains', readonly=True)
    domain_error = fields.Integer(string='Domains in Error', readonly=True)
    customer_total = fields.Integer(string='Customers', readonly=True)
    contact_total = fields.Integer(string='Contacts', readonly=True)
    sync_synced = fields.Integer(string='Synced Records', readonly=True)
    sync_error = fields.Integer(string='Error Records', readonly=True)
    sync_pending = fields.Integer(string='Pending Sync', readonly=True)
    top_customers = fields.Text(string='Top Customers', readonly=True)
    tld_distribution = fields.Text(string='TLD Distribution', readonly=True)
    growth_domains = fields.Text(string='Domain Growth', readonly=True)
    growth_contacts = fields.Text(string='Contact Growth', readonly=True)
    last_sync = fields.Datetime(string='Last Sync', readonly=True)
    stats_html = fields.Html(string='Dashboard', readonly=True)

    @api.model
    def _dashboard_html(self):
        asset_model = self.env['domain.asset']
        partner_model = self.env['res.partner']
        now = fields.Datetime.now()
        previous_window = now - timedelta(days=30)
        older_window = now - timedelta(days=60)

        domain_total = asset_model.search_count([])
        domain_active = asset_model.search_count([('status', '=', 'active')])
        domain_error = asset_model.search_count([('sync_state', '=', 'error')])
        customer_total = len(asset_model.read_group([('partner_id', '!=', False)], ['partner_id'], ['partner_id']))
        contact_domain = [('external_contact_handle', '!=', False)]
        contact_total = partner_model.search_count(contact_domain)
        sync_synced = asset_model.search_count([('sync_state', '=', 'synced')]) + partner_model.search_count(contact_domain + [('sync_state', '=', 'synced')])
        sync_error = asset_model.search_count([('sync_state', '=', 'error')]) + partner_model.search_count(contact_domain + [('sync_state', '=', 'error')])
        sync_pending = asset_model.search_count([('needs_sync', '=', True)]) + partner_model.search_count(contact_domain + [('needs_sync', '=', True)])

        top_customers = asset_model.read_group(
            [('partner_id', '!=', False)],
            ['partner_id'],
            ['partner_id'],
            limit=5,
        )
        customer_lines = []
        for item in top_customers:
            partner = item.get('partner_id')
            if isinstance(partner, tuple) and partner:
                partner_name = partner[1] if len(partner) > 1 else str(partner[0])
                customer_lines.append(f"<li><strong>{escape(partner_name)}</strong>: {item.get('__count', 0)} domains</li>")
        customer_summary = ''.join(customer_lines) or '<li>No customers with domains yet.</li>'
        customer_summary_text = '\n'.join(
            f"{(item.get('partner_id') or ['', 'Unknown'])[1]}: {item.get('__count', 0)} domains"
            for item in top_customers if item.get('partner_id')
        ) or 'No customers with domains yet.'

        tld_groups = asset_model.read_group([('tld', '!=', False)], ['tld'], ['tld'], limit=10)
        tld_lines = []
        for item in tld_groups:
            tld_lines.append(f"<li><strong>{escape(str(item.get('tld') or ''))}</strong>: {item.get('__count', 0)}</li>")
        tld_summary = ''.join(tld_lines) or '<li>No TLD data yet.</li>'
        tld_summary_text = '\n'.join(
            f"{item.get('tld') or 'Unknown'}: {item.get('__count', 0)}"
            for item in tld_groups
        ) or 'No TLD data yet.'

        domain_last_30 = asset_model.search_count([('create_date', '>=', previous_window)])
        domain_prev_30 = asset_model.search_count([('create_date', '>=', older_window), ('create_date', '<', previous_window)])
        contact_last_30 = partner_model.search_count(contact_domain + [('create_date', '>=', previous_window)])
        contact_prev_30 = partner_model.search_count(contact_domain + [('create_date', '>=', older_window), ('create_date', '<', previous_window)])

        def ratio_text(current, previous):
            if previous:
                growth = ((current - previous) / previous) * 100
                return f'{growth:+.1f}%'
            return f'{current:+d} (baseline)'

        last_sync = asset_model.search([('last_sync_at', '!=', False)], order='last_sync_at desc', limit=1)
        last_sync_value = last_sync[0].last_sync_at if last_sync else False

        return {
            'domain_total': domain_total,
            'domain_active': domain_active,
            'domain_error': domain_error,
            'customer_total': customer_total,
            'contact_total': contact_total,
            'sync_synced': sync_synced,
            'sync_error': sync_error,
            'sync_pending': sync_pending,
            'top_customers': customer_summary_text,
            'tld_distribution': tld_summary_text,
            'growth_domains': f"Last 30 days: {domain_last_30} | Previous 30 days: {domain_prev_30} | Δ {ratio_text(domain_last_30, domain_prev_30)}",
            'growth_contacts': f"Last 30 days: {contact_last_30} | Previous 30 days: {contact_prev_30} | Δ {ratio_text(contact_last_30, contact_prev_30)}",
            'last_sync': last_sync_value,
            'stats_html': f"""
                <div class='o_view_manager_content'>
                    <div class='row mt8'>
                        <div class='col-md-2 text-center'><div class='oe_kanban_card'><div class='oe_kanban_content'><strong>{domain_total}</strong><br/>Domains</div></div></div>
                        <div class='col-md-2 text-center'><div class='oe_kanban_card'><div class='oe_kanban_content'><strong>{domain_active}</strong><br/>Active</div></div></div>
                        <div class='col-md-2 text-center'><div class='oe_kanban_card'><div class='oe_kanban_content'><strong>{customer_total}</strong><br/>Customers</div></div></div>
                        <div class='col-md-2 text-center'><div class='oe_kanban_card'><div class='oe_kanban_content'><strong>{contact_total}</strong><br/>Contacts</div></div></div>
                        <div class='col-md-2 text-center'><div class='oe_kanban_card'><div class='oe_kanban_content'><strong>{sync_error}</strong><br/>Errors</div></div></div>
                        <div class='col-md-2 text-center'><div class='oe_kanban_card'><div class='oe_kanban_content'><strong>{sync_pending}</strong><br/>Pending</div></div></div>
                    </div>
                    <div class='row mt8'>
                        <div class='col-md-6'><div class='oe_kanban_card'><div class='oe_kanban_content'><h4>Top customers</h4><ul>{customer_summary}</ul></div></div></div>
                        <div class='col-md-6'><div class='oe_kanban_card'><div class='oe_kanban_content'><h4>TLD distribution</h4><ul>{tld_summary}</ul></div></div></div>
                    </div>
                    <div class='row mt8'>
                        <div class='col-md-6'><div class='oe_kanban_card'><div class='oe_kanban_content'><h4>Domain growth</h4><p>{f"Last 30 days: {domain_last_30} | Previous 30 days: {domain_prev_30} | Δ {ratio_text(domain_last_30, domain_prev_30)}"}</p></div></div></div>
                        <div class='col-md-6'><div class='oe_kanban_card'><div class='oe_kanban_content'><h4>Contact growth</h4><p>{f"Last 30 days: {contact_last_30} | Previous 30 days: {contact_prev_30} | Δ {ratio_text(contact_last_30, contact_prev_30)}"}</p></div></div></div>
                    </div>
                </div>
            """,
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res.update(self._dashboard_html())
        return res

    def refresh_dashboard(self):
        values = self._dashboard_html()
        overview = self[:1]
        if not overview or not overview.id:
            overview = self.create({'name': 'Overview'})
        overview.write(values)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': overview.id,
            'view_mode': 'form',
            'target': 'current',
        }
