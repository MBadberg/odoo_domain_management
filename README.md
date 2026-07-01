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

---

## API Client

The API client is in `services/domainrobot_client.py`.

It implements:
- `check_domain(domain)` – single domain availability (command: `CheckDomain`)
- `check_domains(domains)` – multi-domain availability (command: `CheckDomains`)
- `register_domain(...)` – domain registration (command: `adddomain`)
- `add_contact(...)` – contact handle creation (command: `addcontact`)
- `status_user()` – account status (command: `statusUser`)
- `status_domain(domain)` – domain status **TODO** (command: `StatusDomain` – verify from PDF handbook)

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
2. **Domain renewal / transfer / DNS** are not yet implemented – only stubs exist.
3. **`StatusDomain` command name** needs verification against the API handbook PDF; see `TODO` in `domainrobot_client.py`.
4. **Payment integration** is not included – the module registers domains directly; invoice/payment workflows must be added separately.
5. The cron job for status synchronisation is **disabled by default** – enable it after implementing `status_domain()`.

---

## References

- `API_Manual_domain_robot.pdf` – full API handbook (bundled in this repository)
- `PHP_API_Example.zip` – reference PHP examples (bundled in this repository)
- API base URL: `https://api.domainreselling.de/api/call.cgi`
