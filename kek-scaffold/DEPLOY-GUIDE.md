# KEK Dashboard — Azure Static Web Apps Deployment Guide

## What's in this folder

| File | Purpose |
|------|---------|
| `index.html` | KEK Holdings sales dashboard (4 outlets BM/TP/PG/WIB) |
| `staticwebapp.config.json` | Auth + routing — locks access to your Microsoft tenant |
| `scripts/` | Deterministic Python pipeline (parse POS → build views → swap inline DATA) |
| `pos_inbox/` | Per-day POS files (auto-populated by the daily workflow) |
| `historical/` | Frozen historical batch files (one-time bootstrap, see CLOUD-ROUTINE-SETUP.md) |
| `.github/workflows/update-dashboard.yml` | Daily refresh job |

---

## Step-by-step setup

### 1. Create the Azure Static Web App

1. Portal → **Static Web Apps** → **+ Create**
2. Fill in:
   - **Subscription**: your Azure subscription
   - **Resource Group**: reuse `rg-pe-dashboard` or create `rg-kek-dashboard`
   - **Name**: `kek-dashboard`
   - **Plan type**: **Free**
   - **Region**: East Asia
   - **Deployment source**: **GitHub** → connect to `tanjz-ap/kek_dashboard_live`, branch `main`
   - **Build presets**: **Custom** with `app_location=/`, `api_location=`, `output_location=`
3. **Review + Create** → **Create**
4. Note the URL (e.g. `https://<random>.azurestaticapps.net`).

Connecting via GitHub will auto-create an `azure-static-web-apps-<name>.yml` workflow in `.github/workflows/`. Leave it as-is — the daily `update-dashboard.yml` calls the same deploy action explicitly so both paths trigger a deploy.

### 2. Register an Azure AD app (tenant-locked auth)

1. Portal → **Microsoft Entra ID** → **App registrations** → **+ New registration**
2. Fill in:
   - **Name**: `KEK Dashboard`
   - **Supported account types**: **Single tenant**
   - **Redirect URI**: Web → `https://<your-swa-url>/.auth/login/aad/callback`
3. **Register**.
4. Copy **Application (client) ID** and **Directory (tenant) ID**.
5. **Certificates & secrets** → **+ New client secret** → copy the **Value** immediately.

### 3. Configure the SWA with AAD credentials

1. SWA in Azure Portal → **Settings** → **Configuration** → **Application settings**
2. Add:
   - `AAD_CLIENT_ID` = Application (client) ID from step 2
   - `AAD_CLIENT_SECRET` = client secret value from step 2
3. **Save**.

### 4. Wire the SWA deployment token into GitHub

1. SWA → **Overview** → **Manage deployment token** → copy.
2. GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
3. Name: `AZURE_STATIC_WEB_APPS_API_TOKEN_KEK`. Value: the token. Save.

(The GitHub-connected SWA also creates its own auto-generated token secret with a name like `AZURE_STATIC_WEB_APPS_API_TOKEN_<RANDOM>`. You can either point the explicit deploy step in `update-dashboard.yml` at that secret name instead, or keep `AZURE_STATIC_WEB_APPS_API_TOKEN_KEK` and copy the same token value into both. Either works.)

### 5. First deploy

Push the scaffold to `main` (or wait for the daily cron). The GitHub-connected SWA workflow deploys `index.html` automatically on push. Visit the URL — you should be redirected to Microsoft login. Only your tenant's accounts can sign in.

---

## How authentication works

`staticwebapp.config.json` locks every route to authenticated users and redirects 401s to `/.auth/login/aad`. The "single tenant" setting on the AAD app registration means non-tenant accounts can't authenticate. External users see a Microsoft login error.

---

## Updating the dashboard

The daily `update-dashboard.yml` workflow handles this automatically — see `CLOUD-ROUTINE-SETUP.md`. For manual updates, edit `index.html` directly and push to `main`; the GitHub-connected SWA workflow auto-deploys.

---

## Optional: Custom domain

1. SWA → **Custom domains** → **+ Add**
2. Add a CNAME record pointing your subdomain (e.g. `kek-dashboard.argilepartners.com`) to the SWA URL.
3. Azure handles HTTPS certificates automatically.
