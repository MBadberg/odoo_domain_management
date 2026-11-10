# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    external_contact_handle = fields.Char(
        string='Domainrobot Contact Handle',
        copy=False,
        index=True,
        help='External contact handle returned by Domainrobot for this customer.',
    )
    last_sync_at = fields.Datetime(string='Last Sync', index=True, copy=False)
    sync_state = fields.Selection(
        [('draft', 'Draft'), ('synced', 'Synced'), ('error', 'Error')],
        default='draft',
        index=True,
        copy=False,
        string='Sync State',
    )
    sync_error = fields.Text(string='Sync Error', copy=False)
    needs_sync = fields.Boolean(string='Needs Sync', default=False, index=True, copy=False)

    def _sync_single_contact_handle(self):
        self.ensure_one()
        if self.env.context.get('skip_domainrobot_sync'):
            return self.external_contact_handle
        try:
            from odoo.addons.odoo_domain_management.services.domainrobot_sync import DomainrobotSyncService
            service = DomainrobotSyncService(self.env)
            service.sync_partner(self)
        except Exception as exc:  # pragma: no cover - defensive guard
            _logger.warning('Could not sync contact handle for partner %s: %s', self.name or self.id, exc)
            self.with_context(skip_domainrobot_sync=True).write({
                'sync_state': 'error',
                'sync_error': str(exc),
                'needs_sync': True,
            })
        return self.external_contact_handle

    def action_sync_domainrobot_contact(self):
        for rec in self:
            rec._sync_single_contact_handle()
        return True

    def _create_or_sync_contact_handle(self):
        self.ensure_one()
        if self.external_contact_handle:
            return self.external_contact_handle
        self._sync_single_contact_handle()
        return self.external_contact_handle

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.env.context.get('skip_domainrobot_sync'):
                continue
            rec._sync_single_contact_handle()
        return records

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get('skip_domainrobot_sync'):
            return result
        fields_to_sync = {'name', 'email', 'phone', 'street', 'street2', 'zip', 'city', 'state_id', 'country_id', 'company_name'}
        if fields_to_sync.intersection(vals.keys()):
            for rec in self:
                rec._sync_single_contact_handle()
        return result
