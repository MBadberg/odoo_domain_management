# -*- coding: utf-8 -*-
import logging

from odoo import fields

from .domainrobot_client import DomainrobotAPIError, DomainrobotClient

_logger = logging.getLogger(__name__)


class DomainrobotSyncService:
    """Central point for safely synchronising Odoo and Domainrobot data."""

    def __init__(self, env):
        self.env = env
        self.client = None
        try:
            self.client = DomainrobotClient.from_system_params(env)
        except DomainrobotAPIError:
            _logger.debug('Domainrobot credentials not configured; sync service will retry when configured.', exc_info=True)

    @staticmethod
    def normalize_domain_name(value):
        if not value:
            return ''
        return str(value).strip().lower()

    @staticmethod
    def _as_list(value):
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value if v not in (None, '')]
        return [str(value)]

    @staticmethod
    def _extract_property_values(result, *keys):
        properties = (result or {}).get('properties', {}) or {}
        for key in keys:
            values = properties.get(key.upper()) or properties.get(key)
            if values:
                return [str(v) for v in (values if isinstance(values, list) else [values]) if v not in (None, '')]
        for key in properties:
            if key.upper() in {k.upper() for k in keys}:
                values = properties[key]
                return [str(v) for v in (values if isinstance(values, list) else [values]) if v not in (None, '')]
        return []

    @staticmethod
    def _first_property_value(result, *keys):
        values = DomainrobotSyncService._extract_property_values(result, *keys)
        return values[0] if values else ''

    @staticmethod
    def _partner_name(partner):
        if not partner:
            return ''
        if partner.name:
            return partner.name
        names = [partner.firstname or '', partner.lastname or '']
        return ' '.join(filter(None, names)).strip() or partner.email or 'Customer'

    @staticmethod
    def _contact_payload(partner):
        country_code = ''
        if getattr(partner, 'country_id', False) and partner.country_id.code:
            country_code = partner.country_id.code.upper()
        street = partner.street or ''
        if partner.street2:
            street = f"{street} {partner.street2}".strip()
        firstname = partner.firstname or (partner.name or '').split()[0] if partner.name else ''
        lastname = partner.lastname or ' '.join((partner.name or '').split()[1:]) if partner.name else ''
        return {
            'firstname': firstname or 'Customer',
            'lastname': lastname or 'Domain',
            'street': street,
            'zip_code': partner.zip or '',
            'city': partner.city or '',
            'country': country_code or 'DE',
            'phone': partner.phone or '',
            'email': partner.email or '',
            'organization': partner.company_name or '',
            'state': partner.state_id.code or partner.state_id.name or '',
        }

    def _get_client(self):
        if self.client is None:
            self.client = DomainrobotClient.from_system_params(self.env)
        return self.client

    def _write_sync_state(self, record, state='synced', error='', needs_sync=False):
        if not record or self.env.context.get('skip_domainrobot_sync'):
            return record
        vals = {
            'last_sync_at': fields.Datetime.now(),
            'sync_state': state,
            'sync_error': error or '',
            'needs_sync': needs_sync,
        }
        record.with_context(skip_domainrobot_sync=True).write(vals)
        return record

    def sync_partner(self, partner):
        if not partner or self.env.context.get('skip_domainrobot_sync'):
            return partner

        handle = partner.external_contact_handle or ''
        payload = self._contact_payload(partner)
        client = self._get_client()
        try:
            if not handle:
                result = client.add_contact(**payload)
                handle = self._first_property_value(result, 'CONTACT', 'CONTACTHANDLE', 'HANDLE')
                if handle:
                    partner.with_context(skip_domainrobot_sync=True).write({'external_contact_handle': handle})
            else:
                result = client.modify_contact(handle, **payload)
            if handle:
                self._write_sync_state(partner, state='synced', error='', needs_sync=False)
                partner.with_context(skip_domainrobot_sync=True).write({'external_contact_handle': handle})
                return partner
            self._write_sync_state(partner, state='error', error='Domainrobot contact handle was not returned by the API.', needs_sync=True)
            return partner
        except DomainrobotAPIError as exc:
            _logger.warning('Domainrobot partner sync failed for %s: %s', partner.name or partner.id, exc)
            self._write_sync_state(partner, state='error', error=exc.description or str(exc), needs_sync=True)
            return partner
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            _logger.exception('Unexpected error while syncing partner %s to Domainrobot', partner.name or partner.id)
            self._write_sync_state(partner, state='error', error=str(exc), needs_sync=True)
            return partner

    def sync_domain_record(self, asset):
        if not asset or self.env.context.get('skip_domainrobot_sync'):
            return asset
        name = self.normalize_domain_name(asset.name)
        if not name:
            return asset
        client = self._get_client()
        try:
            partner_handle = ''
            if asset.partner_id and asset.partner_id.external_contact_handle:
                partner_handle = asset.partner_id.external_contact_handle
            elif asset.partner_id:
                partner_handle = asset.partner_id.with_context(skip_domainrobot_sync=True)._sync_single_contact_handle() if hasattr(asset.partner_id, '_sync_single_contact_handle') else ''

            payload = {}
            if partner_handle:
                payload['ownercontact0'] = partner_handle
            if asset.nameserver0:
                payload['nameserver0'] = asset.nameserver0
            if asset.nameserver1:
                payload['nameserver1'] = asset.nameserver1
            if asset.nameserver2:
                payload['nameserver2'] = asset.nameserver2
            if payload:
                client.modify_domain(name, **payload)

            status_result = client.status_domain(name)
            external_id = self._first_property_value(status_result, 'DOMAINID', 'EXTERNAL_DOMAIN_ID', 'ID') or asset.external_domain_id
            if external_id:
                asset.with_context(skip_domainrobot_sync=True).write({'external_domain_id': external_id})

            status = self._first_property_value(status_result, 'STATUS', 'DOMAINSTATUS', 'STATE')
            if status:
                mapping = {
                    'active': 'active',
                    'paid': 'active',
                    'expired': 'expired',
                    'pending_transfer': 'pending_transfer',
                    'cancelled': 'cancelled',
                }
                asset.with_context(skip_domainrobot_sync=True).write({
                    'status': mapping.get(status.lower(), asset.status or 'unknown'),
                })

            expiry = self._first_property_value(status_result, 'EXPIRYDATE', 'DATE_EXPIRY', 'EXPIRY', 'EXPIRES')
            if expiry:
                try:
                    asset.with_context(skip_domainrobot_sync=True).write({'date_expiry': expiry[:10]})
                except Exception:
                    pass

            self._write_sync_state(asset, state='synced', error='', needs_sync=False)
            return asset
        except DomainrobotAPIError as exc:
            _logger.warning('Domainrobot domain sync failed for %s: %s', asset.name, exc)
            self._write_sync_state(asset, state='error', error=exc.description or str(exc), needs_sync=True)
            return asset
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            _logger.exception('Unexpected error while syncing domain %s to Domainrobot', asset.name)
            self._write_sync_state(asset, state='error', error=str(exc), needs_sync=True)
            return asset

    def sync_transfer_record(self, transfer):
        if not transfer or self.env.context.get('skip_domainrobot_sync'):
            return transfer
        if not transfer.name:
            return transfer
        client = self._get_client()
        try:
            result = client.query_transfer_list() if transfer.transfer_type == 'incoming' else client.query_foreign_transfer_list()
            transfer_id = self._first_property_value(result, 'TRANSFERID', 'EXTERNAL_TRANSFER_ID', 'ID') or transfer.external_transfer_id
            if transfer_id:
                transfer.with_context(skip_domainrobot_sync=True).write({'external_transfer_id': transfer_id})
            api_code = result.get('code')
            if api_code:
                transfer.with_context(skip_domainrobot_sync=True).write({'api_response_code': api_code})
            if result.get('description'):
                transfer.with_context(skip_domainrobot_sync=True).write({'api_response_message': result.get('description')})
            self._write_sync_state(transfer, state='synced', error='', needs_sync=False)
            return transfer
        except DomainrobotAPIError as exc:
            _logger.warning('Domainrobot transfer sync failed for %s: %s', transfer.name, exc)
            self._write_sync_state(transfer, state='error', error=exc.description or str(exc), needs_sync=True)
            return transfer
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            _logger.exception('Unexpected error while syncing transfer %s to Domainrobot', transfer.name)
            self._write_sync_state(transfer, state='error', error=str(exc), needs_sync=True)
            return transfer

    def import_contacts(self):
        client = self._get_client()
        result = client.query_contact_list()
        handles = self._extract_property_values(result, 'CONTACT', 'CONTACTLIST', 'CONTACT_HANDLE', 'HANDLE')
        if not handles:
            return []

        partner_model = self.env['res.partner']
        synced = []
        for handle in handles:
            contact = partner_model.search([('external_contact_handle', '=', handle)], limit=1)
            if contact:
                contact.with_context(skip_domainrobot_sync=True).write({'last_sync_at': fields.Datetime.now(), 'sync_state': 'synced', 'sync_error': '', 'needs_sync': False})
                synced.append(contact)
                continue
            vals = {
                'name': handle,
                'external_contact_handle': handle,
                'last_sync_at': fields.Datetime.now(),
                'sync_state': 'synced',
                'sync_error': '',
                'needs_sync': False,
            }
            new_contact = partner_model.with_context(skip_domainrobot_sync=True).create(vals)
            synced.append(new_contact)
        return synced

    def import_domains(self):
        client = self._get_client()
        result = client.query_domain_list()
        domain_names = self._extract_property_values(result, 'DOMAIN', 'DOMAINLIST', 'DOMAINS', 'NAME')
        if not domain_names:
            return []

        asset_model = self.env['domain.asset']
        imported = []
        for domain_name in domain_names:
            normalized = self.normalize_domain_name(domain_name)
            if not normalized:
                continue
            record = asset_model.search([
                '|',
                ('external_domain_id', '=', self._first_property_value(result, 'DOMAINID', 'EXTERNAL_DOMAIN_ID', 'ID') or ''),
                ('name', '=', normalized),
            ], limit=1)
            vals = {
                'name': normalized,
                'external_domain_id': self._first_property_value(result, 'DOMAINID', 'EXTERNAL_DOMAIN_ID', 'ID') or '',
                'status': 'unknown',
                'last_sync_at': fields.Datetime.now(),
                'sync_state': 'synced',
                'sync_error': '',
                'needs_sync': False,
            }
            if record:
                record.with_context(skip_domainrobot_sync=True).write(vals)
                imported.append(record)
            else:
                imported.append(asset_model.with_context(skip_domainrobot_sync=True).create(vals))
        return imported

    def import_transfers(self):
        client = self._get_client()
        models = [
            ('incoming', client.query_transfer_list),
            ('outgoing', client.query_foreign_transfer_list),
        ]
        transfers = []
        for transfer_type, fetcher in models:
            result = fetcher()
            transfer_names = self._extract_property_values(result, 'DOMAIN', 'DOMAINNAME', 'NAME', 'TRANSFERDOMAIN')
            for idx, domain_name in enumerate(transfer_names):
                ref = self._extract_property_values(result, 'TRANSFERID', 'ID', 'TRANSFERIDLIST')[idx] if idx < len(self._extract_property_values(result, 'TRANSFERID', 'ID', 'TRANSFERIDLIST')) else ''
                transfer_rec = self.env['domain.transfer'].search([
                    '|',
                    ('external_transfer_id', '=', ref),
                    ('name', '=', domain_name),
                ], limit=1)
                vals = {
                    'name': domain_name,
                    'transfer_type': transfer_type,
                    'external_transfer_id': ref,
                    'api_response_code': result.get('code', ''),
                    'api_response_message': result.get('description', ''),
                    'status': 'pending',
                    'last_sync_at': fields.Datetime.now(),
                    'sync_state': 'synced',
                    'sync_error': '',
                    'needs_sync': False,
                }
                if transfer_rec:
                    transfer_rec.with_context(skip_domainrobot_sync=True).write(vals)
                    transfers.append(transfer_rec)
                else:
                    transfers.append(self.env['domain.transfer'].with_context(skip_domainrobot_sync=True).create(vals))
        return transfers

    def sync_account(self):
        client = self._get_client()
        account = self.env['domain.account'].search([], limit=1)
        if not account:
            account = self.env['domain.account'].with_context(skip_domainrobot_sync=True).create({'name': 'Main Account'})
        result = client.status_user()
        account.with_context(skip_domainrobot_sync=True).write({
            'api_response_code': result.get('code', ''),
            'api_response_message': result.get('description', ''),
            'account_status': result.get('description', ''),
            'last_sync': fields.Datetime.now(),
            'sync_state': 'synced',
            'sync_error': '',
            'needs_sync': False,
        })
        return account
