# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _post_process_after_done(self):
        res = super()._post_process_after_done()
        for tx in self:
            for order in tx.sale_order_ids:
                try:
                    order._register_domains_after_payment()
                except Exception as exc:  # pylint: disable=broad-except
                    _logger.exception(
                        'Domain processing after payment failed for %s: %s',
                        order.name, exc)
        return res
