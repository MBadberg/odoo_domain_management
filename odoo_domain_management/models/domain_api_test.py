# -*- coding: utf-8 -*-
import json

from odoo import fields, models, _
from odoo.exceptions import UserError


class DomainApiTester(models.TransientModel):
    """Helper model for manually testing Domainrobot API commands from the backend."""

    _name = 'domain.api.test'
    _description = 'Domainrobot API Test'

    command = fields.Selection(
        selection=[
            ('status_user', 'statusUser'),
            ('check_domain', 'CheckDomain'),
            ('check_domains', 'CheckDomains'),
            ('status_domain', 'StatusDomain'),
            ('add_contact', 'addcontact'),
        ],
        string='API Command',
        default='status_user',
        required=True,
    )
    domain_name = fields.Char(string='Domain Name')
    domains = fields.Text(
        string='Domains',
        help='Comma-separated or newline-separated list of domains.',
    )
    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    street = fields.Char(string='Street')
    zip_code = fields.Char(string='ZIP Code')
    city = fields.Char(string='City')
    country = fields.Char(string='Country', default='DE')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    response_code = fields.Char(string='Response Code', readonly=True)
    response_description = fields.Text(string='Response Description', readonly=True)
    raw_response = fields.Text(string='Raw API Response', readonly=True)
    result_payload = fields.Text(string='Parsed Result', readonly=True)

    def action_test_api(self):
        """Execute the selected Domainrobot API command and store the response."""
        self.ensure_one()
        client = self._get_client()
        payload = self._build_payload()
        result = client.execute_command(payload)

        self.write({
            'response_code': result.get('code', ''),
            'response_description': result.get('description', ''),
            'raw_response': result.get('raw_response', ''),
            'result_payload': json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False),
        })

        action = {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

        if result.get('code') not in ('200', '210', '211'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('API call failed'),
                    'message': '%s - %s' % (
                        result.get('code', 'unknown'),
                        result.get('description', 'No description returned'),
                    ),
                    'type': 'danger',
                    'next': action,
                },
            }

        return action

    def action_clear(self):
        self.write({
            'response_code': False,
            'response_description': False,
            'raw_response': False,
            'result_payload': False,
        })
        return True

    def _build_payload(self):
        """Translate the form values into the matching Domainrobot API payload."""
        command = self.command
        if command == 'status_user':
            return {'command': 'statusUser'}
        if command == 'check_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for CheckDomain.'))
            return {'command': 'CheckDomain', 'domain': self.domain_name}
        if command == 'check_domains':
            domains = self._split_domains()
            if not domains:
                raise UserError(_('At least one domain is required for CheckDomains.'))
            payload = {'command': 'CheckDomains'}
            for idx, domain in enumerate(domains):
                payload[f'domain{idx}'] = domain
            return payload
        if command == 'status_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for StatusDomain.'))
            return {'command': 'StatusDomain', 'domain': self.domain_name}
        if command == 'add_contact':
            if not self.first_name or not self.last_name or not self.street or not self.city:
                raise UserError(_('First name, last name, street and city are required for addcontact.'))
            return {
                'command': 'addcontact',
                'firstname': self.first_name,
                'lastname': self.last_name,
                'street': self.street,
                'zip': self.zip_code or '',
                'city': self.city,
                'country': self.country or 'DE',
                'phone': self.phone or '',
                'email': self.email or '',
            }
        raise UserError(_('Unsupported API command: %s') % command)

    def _split_domains(self):
        raw_domains = (self.domains or '').replace('\r', '\n')
        parts = []
        for line in raw_domains.split('\n'):
            for value in line.split(','):
                value = value.strip()
                if value:
                    parts.append(value)
        return parts

    def _get_client(self):
        from odoo.addons.odoo_domain_management.services.domainrobot_client import DomainrobotClient
        return DomainrobotClient.from_system_params(self.env)
