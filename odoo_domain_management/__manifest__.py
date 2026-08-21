# -*- coding: utf-8 -*-
{
    'name': 'Domain Management (Domainrobot)',
    'version': '19.0.1.0.0',
    'category': 'Website/eCommerce',
    'summary': 'Manage domain registration via the Domainrobot / united-domains Reselling API',
    'description': """
Integrates Odoo 19 Community with the Domainrobot (united-domains Reselling) API.

Features (MVP):
- Domain availability check (single and multi-TLD)
- Domain purchase / registration
- Customer portal: search domains, view "My Domains"
- Admin configuration for API credentials and endpoint
- Extensible API client for future operations (nameservers, DNS, transfer, contacts, renew)
    """,
    'author': 'MBadberg',
    'website': '',
    'depends': [
        'base',
        'base_setup',
        'mail',
        'portal',
        'website',
    ],
    'data': [
        # Security first
        'security/security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/ir_cron.xml',
        # Views
        'views/domain_order_views.xml',
        'views/domain_asset_views.xml',
        'views/domain_transfer_views.xml',
        'views/domain_account_views.xml',
        'views/domain_api_test_views.xml',
        'views/res_config_settings_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo_domain_management/static/src/css/domain_form_fix.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
