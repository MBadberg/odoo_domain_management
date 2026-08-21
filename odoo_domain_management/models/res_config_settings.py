# -*- coding: utf-8 -*-
import json
import os
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    """Extend general settings to configure the Domainrobot API credentials."""

    _inherit = 'res.config.settings'

    # ── API configuration fields ──────────────────────────────────────────────

    domainrobot_api_url = fields.Char(
        string='API Endpoint URL',
        default='https://api.domainreselling.de/api/call.cgi',
        config_parameter='domainrobot.api_url',
        help='Base URL of the Domainrobot/united-domains Reselling API.',
    )
    domainrobot_api_user = fields.Char(
        string='API Username (s_login)',
        config_parameter='domainrobot.api_user',
        help='Login name for the Domainrobot API.',
    )
    domainrobot_api_password = fields.Char(
        string='API Password (s_pw)',
        config_parameter='domainrobot.api_password',
        help='Password / token for the Domainrobot API. Stored as a system parameter.',
    )
    domainrobot_api_timeout = fields.Integer(
        string='API Timeout (seconds)',
        default=30,
        config_parameter='domainrobot.api_timeout',
        help='HTTP request timeout in seconds.',
    )

    # ── Update configuration fields ───────────────────────────────────────────

    module_version = fields.Char(
        string='Installed version',
        readonly=True,
        default='19.0.1.1.0',
        help='Current version of this Odoo addon as defined in the module manifest.',
    )
    github_repository_url = fields.Char(
        string='GitHub repository URL',
        config_parameter='odoo_domain_management.github_repository_url',
        default='https://github.com/MBadberg/odoo_domain_management',
        help='Repository URL used to check for and pull updates from GitHub.',
    )
    github_update_branch = fields.Char(
        string='GitHub update branch',
        config_parameter='odoo_domain_management.github_update_branch',
        default='main',
        help='Git branch or tag to use when checking for updates.',
    )
    github_latest_version = fields.Char(
        string='Latest GitHub version',
        readonly=True,
        default='-',
        help='Latest version reported by the GitHub release API.',
    )
    github_update_available = fields.Boolean(
        string='Update available',
        readonly=True,
        default=False,
    )
    github_last_check = fields.Datetime(
        string='Last update check',
        readonly=True,
        help='Timestamp of the last GitHub update check.',
    )

    @api.model
    def _get_module_version(self):
        module = self.env['ir.module.module'].sudo().search([
            ('name', '=', 'odoo_domain_management'),
            ('state', '!=', 'uninstalled'),
        ], limit=1)
        if module and module.latest_version:
            return module.latest_version
        return self.env['ir.module.module']._get_module_info('odoo_domain_management').get('version', '19.0.1.1.0')

    @staticmethod
    def _normalize_version(version):
        if not version:
            return []
        cleaned = version.strip().replace('v', '', 1).strip()
        cleaned = re.sub(r'[^0-9.]', '', cleaned)
        if not cleaned:
            return []
        return [int(part) for part in cleaned.split('.') if part]

    @staticmethod
    def _is_newer_version(candidate, current):
        candidate_parts = ResConfigSettings._normalize_version(candidate)
        current_parts = ResConfigSettings._normalize_version(current)
        max_len = max(len(candidate_parts), len(current_parts))
        candidate_parts += [0] * (max_len - len(candidate_parts))
        current_parts += [0] * (max_len - len(current_parts))
        return tuple(candidate_parts) > tuple(current_parts)

    def _github_repo_parts(self):
        repo_url = (self.github_repository_url or '').strip().rstrip('/')
        if not repo_url:
            return False, _('Please configure a GitHub repository URL first.')
        if 'github.com/' not in repo_url:
            return False, _('The repository URL must point to GitHub.')
        repo_path = repo_url.split('github.com/', 1)[1]
        parts = [p.rstrip('.git') for p in repo_path.split('/') if p]
        if len(parts) < 2:
            return False, _('GitHub URL must have the form https://github.com/<owner>/<repository>.')
        return parts[0], parts[1]

    def _fetch_latest_github_version(self):
        owner, repo = self._github_repo_parts()
        if not owner:
            return False, repo
        api_url = f'https://api.github.com/repos/{owner}/{repo}/releases/latest'
        request = Request(api_url, headers={'User-Agent': 'odoo-domain-management-updater'})
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (HTTPError, URLError, ValueError):
            return False, _('Could not read the GitHub release metadata for this repository.')
        tag = (payload.get('tag_name') or '').strip()
        if not tag:
            return False, _('No GitHub release tag was found for this repository.')
        return tag, False

    def _get_current_module_version(self):
        get_module_info = getattr(self.env['ir.module.module'], '_get_module_info', None)
        if callable(get_module_info):
            version = get_module_info('odoo_domain_management').get('version')
            if version:
                return version
        try:
            from odoo_domain_management import __version__ as module_version
            return module_version
        except ImportError:
            return '19.0.1.1.0'

    def _git_repo_root(self):
        module_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        repo_root = os.path.dirname(module_dir)
        if os.path.isdir(os.path.join(repo_root, '.git')):
            return repo_root
        if os.path.isdir(os.path.join(module_dir, '.git')):
            return module_dir
        return repo_root

    def _run_git_command(self, arguments):
        repo_root = self._git_repo_root()
        result = subprocess.run(
            ['git', '-C', repo_root] + arguments,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise UserError(_(result.stderr or 'git command failed.'))
        return result.stdout.strip()

    def action_check_github_update(self):
        latest_version, error = self._fetch_latest_github_version()
        if error:
            raise UserError(error)
        self.github_latest_version = latest_version
        self.github_update_available = self._is_newer_version(latest_version, self._get_current_module_version())
        self.github_last_check = fields.Datetime.now()
        self.module_version = self._get_current_module_version()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.config.settings',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_update_from_github(self):
        repository_url = (self.github_repository_url or '').strip()
        if not repository_url:
            raise UserError(_('Please configure the GitHub repository URL before updating.'))
        branch = (self.github_update_branch or 'main').strip() or 'main'
        repo_root = self._git_repo_root()
        if not os.path.isdir(os.path.join(repo_root, '.git')):
            raise UserError(_('The module is not located in a git checkout, so it cannot be updated from GitHub.'))
        try:
            current_remote = self._run_git_command(['remote', 'get-url', 'origin'])
            normalized_current = current_remote[:-4] if current_remote.endswith('.git') else current_remote
            normalized_repository = repository_url[:-4] if repository_url.endswith('.git') else repository_url
            if current_remote != repository_url and current_remote and normalized_current != normalized_repository:
                self._run_git_command(['remote', 'set-url', 'origin', repository_url])
        except UserError:
            self._run_git_command(['remote', 'add', 'origin', repository_url])
        self._run_git_command(['fetch', '--all', '--tags'])
        self._run_git_command(['pull', '--ff-only', 'origin', branch])
        self.env['ir.module.module'].search([('name', '=', 'odoo_domain_management')]).button_immediate_upgrade()
        self.module_version = self._get_current_module_version()
        self.github_latest_version = self._fetch_latest_github_version()[0]
        self.github_update_available = False
        self.github_last_check = fields.Datetime.now()
        return {'type': 'ir.actions.act_window_close'}
