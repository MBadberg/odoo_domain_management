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
            ('modify_domain', 'ModifyDomain'),
            ('delete_domain', 'DeleteDomain'),
            ('trade_domain', 'TradeDomain'),
            ('push_domain', 'PushDomain'),
            ('sync_domain', 'SyncDomain'),
            ('set_domain_renewal_mode', 'SetDomainRenewalMode'),
            ('renew_domain', 'RenewDomain'),
            ('transfer_domain', 'TransferDomain'),
            ('check_domain_transfer', 'CheckDomainTransfer'),
            ('activate_domain_transfer', 'ActivateDomainTransfer'),
            ('query_domain_list', 'QueryDomainList'),
            ('query_transfer_list', 'QueryTransferList'),
            ('query_foreign_transfer_list', 'QueryForeignTransferList'),
            ('check_domain_application', 'CheckDomainApplication'),
            ('query_domain_application_list', 'QueryDomainApplicationList'),
            ('status_domain_application', 'StatusDomainApplication'),
            ('add_domain_application', 'AddDomainApplication'),
            ('delete_domain_application', 'DeleteDomainApplication'),
            ('pay_domain_application', 'PayDomainApplication'),
            ('add_contact', 'addcontact'),
            ('modify_contact', 'ModifyContact'),
            ('status_contact', 'StatusContact'),
            ('delete_contact', 'DeleteContact'),
            ('clone_contact', 'CloneContact'),
            ('query_contact_list', 'QueryContactList'),
            ('check_nameserver', 'CheckNameserver'),
            ('add_nameserver', 'AddNameserver'),
            ('modify_nameserver', 'ModifyNameserver'),
            ('status_nameserver', 'StatusNameserver'),
            ('delete_nameserver', 'DeleteNameserver'),
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
    contact_handle = fields.Char(string='Contact Handle')
    nameserver_name = fields.Char(string='Nameserver')
    application_id = fields.Char(string='Application ID')
    class_name = fields.Char(string='Class')
    period_value = fields.Char(string='Period')
    renewal_mode = fields.Char(string='Renewal Mode')
    transfer_action = fields.Char(string='Transfer Action', default='REQUEST')
    target = fields.Char(string='Push Target')
    ip_address = fields.Char(string='IP Address')
    extra_fields = fields.Text(string='Additional Parameters', help='Use key=value pairs, one per line or separated by ampersands.')
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

        if result.get('code') not in ('200', '210', '211', '212', '213', '218', '219'):
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
        extra = self._parse_extra_fields()

        if command == 'status_user':
            return {'command': 'statusUser'}
        if command == 'check_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for CheckDomain.'))
            return {'command': 'CheckDomain', 'domain': self.domain_name, **extra}
        if command == 'check_domains':
            domains = self._split_domains()
            if not domains:
                raise UserError(_('At least one domain is required for CheckDomains.'))
            payload = {'command': 'CheckDomains'}
            for idx, domain in enumerate(domains):
                payload[f'domain{idx}'] = domain
            payload.update(extra)
            return payload
        if command == 'status_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for StatusDomain.'))
            return {'command': 'StatusDomain', 'domain': self.domain_name, **extra}
        if command == 'modify_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for ModifyDomain.'))
            payload = {'command': 'ModifyDomain', 'domain': self.domain_name}
            payload.update(extra)
            return payload
        if command == 'delete_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for DeleteDomain.'))
            return {'command': 'DeleteDomain', 'domain': self.domain_name, **extra}
        if command == 'trade_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for TradeDomain.'))
            payload = {'command': 'TradeDomain', 'domain': self.domain_name}
            if self.contact_handle:
                payload['ownercontact0'] = self.contact_handle
            payload.update(extra)
            return payload
        if command == 'push_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for PushDomain.'))
            payload = {'command': 'PushDomain', 'domain': self.domain_name}
            if self.target:
                payload['target'] = self.target
            payload.update(extra)
            return payload
        if command == 'sync_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for SyncDomain.'))
            return {'command': 'SyncDomain', 'domain': self.domain_name, **extra}
        if command == 'set_domain_renewal_mode':
            if not self.domain_name:
                raise UserError(_('A domain name is required for SetDomainRenewalMode.'))
            payload = {'command': 'SetDomainRenewalMode', 'domain': self.domain_name}
            if self.renewal_mode:
                payload['renewalmode'] = self.renewal_mode
            payload.update(extra)
            return payload
        if command == 'renew_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for RenewDomain.'))
            payload = {'command': 'RenewDomain', 'domain': self.domain_name}
            if self.period_value:
                payload['period'] = self.period_value
            payload.update(extra)
            return payload
        if command == 'transfer_domain':
            if not self.domain_name:
                raise UserError(_('A domain name is required for TransferDomain.'))
            payload = {'command': 'TransferDomain', 'domain': self.domain_name}
            if self.transfer_action:
                payload['action'] = self.transfer_action
            payload.update(extra)
            return payload
        if command == 'check_domain_transfer':
            if not self.domain_name:
                raise UserError(_('A domain name is required for CheckDomainTransfer.'))
            return {'command': 'CheckDomainTransfer', 'domain': self.domain_name, **extra}
        if command == 'activate_domain_transfer':
            if not self.domain_name:
                raise UserError(_('A domain name is required for ActivateDomainTransfer.'))
            payload = {'command': 'ActivateDomainTransfer', 'domain': self.domain_name}
            if self.application_id:
                payload['id'] = self.application_id
            if self.target:
                payload['trigger'] = self.target
            payload.update(extra)
            return payload
        if command == 'query_domain_list':
            payload = {'command': 'QueryDomainList'}
            payload.update(extra)
            return payload
        if command == 'query_transfer_list':
            payload = {'command': 'QueryTransferList'}
            payload.update(extra)
            return payload
        if command == 'query_foreign_transfer_list':
            payload = {'command': 'QueryForeignTransferList'}
            payload.update(extra)
            return payload
        if command == 'check_domain_application':
            if not self.domain_name:
                raise UserError(_('A domain name is required for CheckDomainApplication.'))
            payload = {'command': 'CheckDomainApplication', 'domain': self.domain_name}
            if self.class_name:
                payload['class'] = self.class_name
            payload.update(extra)
            return payload
        if command == 'query_domain_application_list':
            payload = {'command': 'QueryDomainApplicationList'}
            payload.update(extra)
            return payload
        if command == 'status_domain_application':
            if not self.application_id:
                raise UserError(_('An application ID is required for StatusDomainApplication.'))
            payload = {'command': 'StatusDomainApplication', 'application': self.application_id}
            payload.update(extra)
            return payload
        if command == 'add_domain_application':
            if not self.domain_name or not self.class_name:
                raise UserError(_('Domain name and application class are required for AddDomainApplication.'))
            payload = {'command': 'AddDomainApplication', 'domain': self.domain_name, 'class': self.class_name}
            if self.period_value:
                payload['period'] = self.period_value
            if self.contact_handle:
                payload['ownercontact0'] = self.contact_handle
            payload.update(extra)
            return payload
        if command == 'delete_domain_application':
            if not self.application_id:
                raise UserError(_('An application ID is required for DeleteDomainApplication.'))
            return {'command': 'DeleteDomainApplication', 'application': self.application_id, **extra}
        if command == 'pay_domain_application':
            if not self.application_id:
                raise UserError(_('An application ID is required for PayDomainApplication.'))
            return {'command': 'PayDomainApplication', 'application': self.application_id, **extra}
        if command == 'add_contact':
            if not self.first_name or not self.last_name or not self.street or not self.city:
                raise UserError(_('First name, last name, street and city are required for addcontact.'))
            payload = {
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
            if self.contact_handle:
                payload['new'] = 1
            payload.update(extra)
            return payload
        if command == 'modify_contact':
            if not self.contact_handle:
                raise UserError(_('A contact handle is required for ModifyContact.'))
            payload = {'command': 'ModifyContact', 'contact': self.contact_handle}
            payload.update(extra)
            return payload
        if command == 'status_contact':
            if not self.contact_handle:
                raise UserError(_('A contact handle is required for StatusContact.'))
            return {'command': 'StatusContact', 'contact': self.contact_handle, **extra}
        if command == 'delete_contact':
            if not self.contact_handle:
                raise UserError(_('A contact handle is required for DeleteContact.'))
            return {'command': 'DeleteContact', 'contact': self.contact_handle, **extra}
        if command == 'clone_contact':
            if not self.contact_handle:
                raise UserError(_('A contact handle is required for CloneContact.'))
            return {'command': 'CloneContact', 'contact': self.contact_handle, **extra}
        if command == 'query_contact_list':
            payload = {'command': 'QueryContactList'}
            payload.update(extra)
            return payload
        if command == 'check_nameserver':
            if not self.nameserver_name:
                raise UserError(_('A nameserver is required for CheckNameserver.'))
            return {'command': 'CheckNameserver', 'nameserver': self.nameserver_name, **extra}
        if command == 'add_nameserver':
            if not self.nameserver_name:
                raise UserError(_('A nameserver is required for AddNameserver.'))
            payload = {'command': 'AddNameserver', 'nameserver': self.nameserver_name}
            if self.ip_address:
                payload['ipaddress0'] = self.ip_address
            payload.update(extra)
            return payload
        if command == 'modify_nameserver':
            if not self.nameserver_name:
                raise UserError(_('A nameserver is required for ModifyNameserver.'))
            payload = {'command': 'ModifyNameserver', 'nameserver': self.nameserver_name}
            if self.ip_address:
                payload['ipaddress0'] = self.ip_address
            payload.update(extra)
            return payload
        if command == 'status_nameserver':
            if not self.nameserver_name:
                raise UserError(_('A nameserver is required for StatusNameserver.'))
            return {'command': 'StatusNameserver', 'nameserver': self.nameserver_name, **extra}
        if command == 'delete_nameserver':
            if not self.nameserver_name:
                raise UserError(_('A nameserver is required for DeleteNameserver.'))
            return {'command': 'DeleteNameserver', 'nameserver': self.nameserver_name, **extra}
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

    def _parse_extra_fields(self):
        values = {}
        raw = (self.extra_fields or '').strip()
        if not raw:
            return values
        field_text = raw.replace('\r', '\n').replace('&', '\n')
        for field in field_text.split('\n'):
            field = field.strip()
            if not field:
                continue
            if '=' in field:
                name, value = field.split('=', 1)
                values[name.strip()] = value.strip()
            else:
                values[field.strip()] = ''
        return values

    def _get_client(self):
        from odoo.addons.odoo_domain_management.services.domainrobot_client import DomainrobotClient
        return DomainrobotClient.from_system_params(self.env)
