# -*- coding: utf-8 -*-
"""
DomainrobotClient
=================
Thin HTTP client for the united-domains Reselling / Domainrobot API.

API protocol summary (derived from bundled PHP examples):
  - Base URL: https://api.domainreselling.de/api/call.cgi
  - Authentication via GET query parameters: s_login, s_pw
  - Commands sent as URL-encoded POST body (key=value pairs)
  - Response: plain-text key=value pairs, one per line
    CODE  = numeric return code
    DESCRIPTION = human-readable status text
    PROPERTY[KEY][n] = property values (multi-value arrays)

Notable return codes:
  200 – command executed successfully
  210 – domain available
  211 – domain NOT available
  5xx – authentication / permission error
  999 – connection error
"""

import logging
import re
import urllib.parse
import urllib.request
import ssl
from typing import Dict, Any

_logger = logging.getLogger(__name__)

# Default API endpoint (sandbox-compatible – same URL, credentials differ)
DEFAULT_API_URL = 'https://api.domainreselling.de/api/call.cgi'
DEFAULT_TIMEOUT = 30

# Fields that must never appear in plain-text logs
_SENSITIVE_KEYS = frozenset({'s_pw', 'password', 'api_password'})


def _mask_sensitive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *data* with sensitive values replaced by '***'."""
    return {k: ('***' if k.lower() in _SENSITIVE_KEYS else v) for k, v in data.items()}


class DomainrobotAPIError(Exception):
    """Raised when the Domainrobot API returns a non-successful response code."""

    def __init__(self, code: str, description: str):
        self.code = code
        self.description = description
        super().__init__(f'Domainrobot API error {code}: {description}')


class DomainrobotClient:
    """
    Client for the Domainrobot (united-domains Reselling) API.

    Usage::

        client = DomainrobotClient(api_url, username, password)
        result = client.check_domain('example.de')
        # result == {'code': '210', 'description': 'Domain available', 'properties': {...}}
    """

    def __init__(self, api_url: str, username: str, password: str, timeout: int = DEFAULT_TIMEOUT):
        self.api_url = api_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_system_params(cls, env) -> 'DomainrobotClient':
        """
        Build a client from Odoo system parameters (ir.config_parameter).
        Reads:
          - domainrobot.api_url
          - domainrobot.api_user
          - domainrobot.api_password
          - domainrobot.api_timeout
        """
        ICP = env['ir.config_parameter'].sudo()
        api_url = ICP.get_param('domainrobot.api_url', DEFAULT_API_URL)
        username = ICP.get_param('domainrobot.api_user', '')
        password = ICP.get_param('domainrobot.api_password', '')
        timeout = int(ICP.get_param('domainrobot.api_timeout', DEFAULT_TIMEOUT))

        if not username or not password:
            raise DomainrobotAPIError(
                '000',
                'Domainrobot API credentials not configured. '
                'Go to Settings → Domain Management to set them.',
            )

        return cls(api_url, username, password, timeout)

    # ── Public API methods ────────────────────────────────────────────────────

    def check_domain(self, domain: str) -> Dict[str, Any]:
        """
        Check availability of a single domain.

        Returns a dict with keys: code, description, properties.
        Code 210 = available, 211 = not available.
        """
        return self._call({'command': 'CheckDomain', 'domain': domain})

    def check_domains(self, domains: list) -> Dict[str, Any]:
        """
        Check availability of multiple domains at once.

        *domains* is a list of fully-qualified domain names.
        Returns code 200 on success; properties['DOMAINCHECK'] contains results.
        """
        cmd = {'command': 'CheckDomains'}
        for i, d in enumerate(domains):
            cmd[f'domain{i}'] = d
        return self._call(cmd)

    def register_domain(
        self,
        domain: str,
        period: int = 1,
        nameserver0: str = 'ns1a.dodns.net',
        nameserver1: str = 'ns2a.dodns.net',
        owner_contact: str = '',
        admin_contact: str = '',
        tech_contact: str = '',
        billing_contact: str = '',
    ) -> Dict[str, Any]:
        """
        Register (add) a domain via the API.

        Returns code 200 on success; the external domain/order ID may be
        contained in properties.
        """
        cmd = {
            'command': 'adddomain',
            'domain': domain,
            'period': str(period),
            'nameserver0': nameserver0,
            'nameserver1': nameserver1,
        }
        if owner_contact:
            cmd['ownercontact0'] = owner_contact
        if admin_contact:
            cmd['admincontact0'] = admin_contact
        if tech_contact:
            cmd['techcontact0'] = tech_contact
        if billing_contact:
            cmd['billingcontact0'] = billing_contact

        return self._call(cmd)

    def add_contact(
        self,
        firstname: str,
        lastname: str,
        street: str,
        zip_code: str,
        city: str,
        country: str = 'DE',
        phone: str = '',
        email: str = '',
    ) -> Dict[str, Any]:
        """
        Create a new contact handle on the Domainrobot platform.

        Returns code 200 and properties['CONTACT'][0] = contact handle.
        """
        return self._call({
            'command': 'addcontact',
            'firstname': firstname,
            'lastname': lastname,
            'street': street,
            'zip': zip_code,
            'city': city,
            'country': country,
            'phone': phone,
            'email': email,
        })

    def status_user(self) -> Dict[str, Any]:
        """
        Retrieve account status (balance, prices, …).

        Returns code 200 on success.
        """
        return self._call({'command': 'statusUser'})

    def status_domain(self, domain: str) -> Dict[str, Any]:
        """
        Retrieve the status of an already-registered domain.

        TODO: verify the exact command name from the API handbook PDF.
        """
        # TODO: confirm command name with API handbook (may be 'StatusDomain')
        return self._call({'command': 'StatusDomain', 'domain': domain})

    # ── Internal HTTP layer ───────────────────────────────────────────────────

    def _call(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an API call.

        1. Build the full URL with auth credentials in query string.
        2. POST the command payload as URL-encoded form data.
        3. Parse the plain-text response.
        4. Return a normalised dict.
        """
        # Build URL: base_url?s_login=<user>&s_pw=<pass>
        auth_params = urllib.parse.urlencode({
            's_login': self.username,
            's_pw': self.password,
        })
        full_url = f'{self.api_url}?{auth_params}'

        # Encode command as POST body
        body = urllib.parse.urlencode(command).encode('utf-8')

        try:
            # Allow self-signed certs in sandbox environments
            ctx = ssl.create_default_context()
            req = urllib.request.Request(
                full_url,
                data=body,
                method='POST',
                headers={
                    'User-Agent': 'odoo_domain_management/1.0',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
        except urllib.error.URLError as exc:
            _logger.error('Domainrobot API connection error: %s', exc)
            raise DomainrobotAPIError('999', f'Connection error: {exc}') from exc
        except Exception as exc:  # pylint: disable=broad-except
            _logger.error('Domainrobot API unexpected error: %s', exc)
            raise DomainrobotAPIError('998', f'Unexpected error: {exc}') from exc

        result = self._parse_response(raw)
        _logger.debug(
            'Domainrobot API response: code=%s description=%s',
            result.get('code'),
            result.get('description'),
        )
        return result

    @staticmethod
    def _parse_response(raw: str) -> Dict[str, Any]:
        """
        Parse the plain-text Domainrobot response into a Python dict.

        The format mirrors the PHP mreg_parse_response implementation:
          CODE = 200
          DESCRIPTION = Command completed successfully
          PROPERTY[KEY][0] = value0
          PROPERTY[KEY][1] = value1
        """
        result: Dict[str, Any] = {
            'code': '',
            'description': '',
            'properties': {},
        }
        prop_re = re.compile(
            r'^PROPERTY\[([^\]]+)\]\[(\d+)\]\s*=\s*(.*)$', re.IGNORECASE
        )

        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith('['):
                continue

            # Try to match PROPERTY[KEY][n] = value
            m = prop_re.match(line)
            if m:
                key = m.group(1).upper()
                idx = int(m.group(2))
                val = m.group(3).strip()
                props = result['properties']
                if key not in props:
                    props[key] = []
                # Extend list if necessary
                while len(props[key]) <= idx:
                    props[key].append('')
                props[key][idx] = val
                continue

            # Otherwise try KEY = VALUE
            if '=' in line:
                key, _, val = line.partition('=')
                key = key.strip().upper()
                val = val.strip()
                if key == 'CODE':
                    result['code'] = val
                elif key == 'DESCRIPTION':
                    result['description'] = val
                # Other top-level keys are ignored for now

        return result
