# -*- coding: utf-8 -*-
from odoo.tests import common, tagged

from odoo.addons.odoo_domain_management.models.res_config_settings import ResConfigSettings


@tagged('post_install', '-at_install')
class TestResConfigSettings(common.TransactionCase):

    def test_normalize_version(self):
        self.assertEqual(ResConfigSettings._normalize_version('19.0.2.2.0'), [19, 0, 2, 2, 0])
        self.assertEqual(ResConfigSettings._normalize_version('v19.0.1'), [19, 0, 1])
        self.assertEqual(ResConfigSettings._normalize_version('no-version'), [])

    def test_parse_remote_tags(self):
        output = (
            'aaaaaaaa\trefs/tags/19.0.1.1.0\n'
            'bbbbbbbb\trefs/tags/19.0.2.2.0\n'
            'cccccccc\trefs/tags/19.0.2.2.0^{}\n'
        )
        tags = ResConfigSettings._parse_remote_tags(output)
        self.assertEqual(sorted(tags), ['19.0.1.1.0', '19.0.2.2.0'])

    def test_parse_remote_tags_empty(self):
        self.assertEqual(ResConfigSettings._parse_remote_tags(''), [])
