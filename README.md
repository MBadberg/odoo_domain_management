# odoo_domain_management

An **Odoo 19 Community** module that integrates with the [united-domains Reselling / Domainrobot API](https://www.ud-reselling.com) to allow customers to search, purchase, and manage domain names directly from the Odoo portal.

---

## Features (MVP)

| Feature | Status |
|---|---|
| Domain availability check (single domain) | ✅ |
| Domain availability check (multi-TLD) | ✅ |
| Domain purchase / registration | ✅ |
| Customer portal – "My Domains" list | ✅ |
| Customer portal – domain detail page | ✅ |
| Customer portal – register new domain | ✅ |
| Admin settings for API credentials | ✅ |
| Backend views (orders & managed domains) | ✅ |
| Record rules (portal users see only own records) | ✅ |
| Cron job skeleton for status sync | ✅ (inactive by default) |
| Bidirectional Domainrobot sync for contacts, domains, and transfers | ✅ |

---

## Installation

1. Copy the `odoo_domain_management` folder into your Odoo `addons` directory.
2. Restart the Odoo server.
3. Go to **Apps**, search for *Domain Management*, and click **Install**.

---

## Configuration

### 1. Set up API credentials

Navigate to **Settings → General Settings** and scroll to the **Domain Management – Domainrobot API** section.

| Field | Description |
|---|---|
| API Endpoint URL | `https://api.domainreselling.de/api/call.cgi` (default, works for both sandbox and production – credentials differ) |
| API Username | Your reseller login (`s_login`) from the united-domains Reselling portal |
| API Password | Your reseller password (`s_pw`) |
| Timeout (s) | HTTP request timeout in seconds (default: 30) |

The credentials are stored as `ir.config_parameter` records (system parameters).

### 2. (Optional) Set a default contact handle

For the portal purchase flow to work out-of-the-box, set a default contact handle:

Go to **Settings → Technical → Parameters → System Parameters** and create:

| Key | Value |
|---|---|
| `domainrobot.default_contact` | Your pre-created contact handle (e.g. `UDRA-12345`) |

You can create contact handles via the **Domain Orders** backend (or extend the module to expose a contact creation form).

---

## Bidirectional sync behaviour

The module now includes a lightweight sync layer that keeps Odoo and Domainrobot aligned without creating duplicate records.

- `res.partner` records gain `external_contact_handle`, `last_sync_at`, `sync_state`, `sync_error`, and `needs_sync`.
- `domain.asset` and `domain.transfer` also track their external IDs and sync metadata.
- A `skip_domainrobot_sync` context flag prevents write loops when sync jobs update records from the API.
- The service layer is implemented in `services/domainrobot_sync.py` and is kept separate from model logic.
- Repeated sync runs use `external_*` identifiers and normalized names as upsert keys, so duplicate imports are avoided.

Cron jobs are available under **Settings → Technical → Automation** for contacts, domains, transfers, and account status sync. They are disabled by default and can be enabled once API credentials are configured.

## How to use

### Check domain availability (Admin / Portal)

**Portal (customer view):**
1. Log in to the Odoo portal (`/web/login`).
2. Navigate to **My Domains** → click **+ Register New Domain** or go to `/my/domains/check`.
3. Enter a domain name and select the TLDs you want to check.
4. Click **Check** to see availability results.

**Backend (admin view):**
1. Go to **Domains → Domain Orders**.
2. Create a new record, enter the domain name.
3. Click **Check Availability**.

### Purchase / register a domain

**Portal:**
After availability results appear, click the **Register** button next to an available domain.

> **Note (MVP limitation):** Contact handles and nameservers must be pre-configured via system parameters or entered manually in the backend order form before the API call succeeds.

**Backend:**
1. After confirming availability, fill in nameservers and contact handles in the order form.
2. Click **Register Domain**.

### View managed domains

Portal customers can see their registered domains at `/my/domains`.

Backend admins can see all managed domains under **Domains → Managed Domains**.

### Test API commands in the backend

Use **Domains → API Test Console** to run manual calls against the Domainrobot API and inspect the raw reply. The tester supports:

- `statusUser`
- `CheckDomain`
- `CheckDomains`
- `StatusDomain`
- `addcontact`

This is the quick way to verify whether the transferred domains are visible from the API and whether credentials / parameters are still valid.

---

## API Client

The API client is in `services/domainrobot_client.py`.

It implements the structured backend command groups documented in the bundled API handbook:
- `check_domain(domain)` / `check_domains(domains)` – domain availability checks
- `register_domain(...)` – domain registration (`adddomain`)
- `modify_domain(...)`, `status_domain(domain)`, `delete_domain(domain)` – domain lifecycle operations
- `transfer_domain(...)`, `check_domain_transfer(domain)`, `activate_domain_transfer(...)` – transfer flows
- `renew_domain(...)`, `set_domain_renewal_mode(...)`, `push_domain(...)`, `sync_domain(...)` – lifecycle and registry maintenance actions
- `query_domain_list(...)`, `query_transfer_list(...)`, `query_foreign_transfer_list(...)` – backend listing and reporting
- `add_contact(...)`, `modify_contact(...)`, `status_contact(...)`, `delete_contact(...)`, `clone_contact(...)`, `query_contact_list(...)` – contact management
- `check_nameserver(...)`, `add_nameserver(...)`, `modify_nameserver(...)`, `status_nameserver(...)`, `delete_nameserver(...)` – nameserver operations
- `check_domain_application(...)`, `query_domain_application_list(...)`, `status_domain_application(...)`, `add_domain_application(...)`, `delete_domain_application(...)`, `pay_domain_application(...)` – domain application flows
- `status_user()` – account status (`statusUser`)

Sensitive values (password) are never written to logs.

---

## Extending the module

The client and models are designed to be extended:

- Add new API commands by adding methods to `DomainrobotClient`.
- Add new model fields to `domain.asset` (e.g. DNS records, authcode).
- Implement `action_sync_status()` in both models once the status command is confirmed.
- Enable the cron job under **Settings → Technical → Automation** for periodic sync.

---

## Known limitations (MVP)

1. **Contact handle creation** is not exposed in the portal – customers must ask the admin to create one, or the admin must extend the portal to include a contact form.
2. **Portal self-service for renewal / transfer / DNS** is not yet implemented – these workflows are currently backend/admin driven.
3. The client uses the `StatusDomain` command as documented in the bundled PDF and implements the documented backend command structure.
4. **Payment integration** is not included – the module registers domains directly; invoice/payment workflows must be added separately.
5. The cron job for status synchronisation is **disabled by default** – enable it after implementing `status_domain()`.

---

## References

- `API_Manual_domain_robot.pdf` – full API handbook (bundled in this repository)
- `PHP_API_Example.zip` – reference PHP examples (bundled in this repository)
- API base URL: `https://api.domainreselling.de/api/call.cgi`
