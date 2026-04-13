# PizzaExpress Dashboard — Azure Static Web Apps Deployment Guide

## What's in this folder

| File | Purpose |
|------|---------|
| `index.html` | Your PE weekly dashboard (copied from Weekly Reports) |
| `staticwebapp.config.json` | Auth + routing config — locks access to your Microsoft tenant |

---

## Step-by-step setup

### 1. Create an Azure Static Web App

1. Go to **portal.azure.com** → search **Static Web Apps** → **+ Create**
2. Fill in:
   - **Subscription**: your Azure subscription
   - **Resource Group**: create new or use existing (e.g. `rg-pe-dashboard`)
   - **Name**: `pe-dashboard` (or similar)
   - **Plan type**: **Free** (sufficient for this)
   - **Region**: pick closest to Singapore (e.g. East Asia)
   - **Deployment source**: **Other** (we'll upload manually for now)
3. Click **Review + Create** → **Create**
4. Once created, go to the resource and note the **URL** (e.g. `https://happy-rock-abc123.azurestaticapps.net`)

### 2. Register an Azure AD App (for tenant-locked auth)

1. Go to **portal.azure.com** → **Azure Active Directory** (or **Microsoft Entra ID**) → **App registrations** → **+ New registration**
2. Fill in:
   - **Name**: `PE Dashboard`
   - **Supported account types**: **Accounts in this organizational directory only** (single tenant)
   - **Redirect URI**: Web → `https://<your-swa-url>/.auth/login/aad/callback`
3. Click **Register**
4. Note the **Application (client) ID** and **Directory (tenant) ID**
5. Go to **Certificates & secrets** → **+ New client secret** → copy the **Value** immediately (you won't see it again)

### 3. Configure the Static Web App with your AAD credentials

1. Go to your Static Web App in Azure Portal
2. **Settings** → **Configuration** → **Application settings**
3. Add these two settings:
   - `AAD_CLIENT_ID` = your Application (client) ID from step 2
   - `AAD_CLIENT_SECRET` = your client secret value from step 2
4. Click **Save**

### 4. Update the config file with your Tenant ID

Open `staticwebapp.config.json` and replace `<YOUR_TENANT_ID>` with your actual Directory (tenant) ID from step 2.

### 5. Deploy the files

**Option A — Azure Portal (easiest for a one-off)**

Unfortunately the portal doesn't support direct file upload for "Other" source. Use the CLI instead.

**Option B — Azure CLI (recommended)**

```bash
# Install SWA CLI if you don't have it
npm install -g @azure/static-web-apps-cli

# From inside this folder ("PE Dashboard - Azure Deploy"):
swa deploy . --deployment-token <YOUR_DEPLOYMENT_TOKEN>
```

To get the deployment token: go to your Static Web App → **Overview** → **Manage deployment token** → copy it.

**Option C — GitHub Actions (best for auto-updates)**

1. Push this folder to a GitHub repo
2. In Azure Portal, go to your Static Web App → **Deployment** → connect to your GitHub repo
3. Azure will auto-create a GitHub Action that deploys on every push

---

## How authentication works

Once deployed, anyone visiting the dashboard URL will be redirected to Microsoft login. Only users with email accounts in **your Microsoft tenant** can sign in. External users will be blocked automatically because the App Registration is set to "single tenant."

---

## Updating the dashboard

Each time the Revenue Agent generates a new weekly dashboard HTML:

1. Copy the new HTML file into this folder as `index.html` (replacing the old one)
2. Re-deploy using the SWA CLI command above

If you set up GitHub Actions (Option C), just commit the updated `index.html` and it auto-deploys.

---

## Optional: Custom domain

1. Go to your Static Web App → **Custom domains** → **+ Add**
2. Add a CNAME record pointing your subdomain (e.g. `dashboard.argilepartners.com`) to the SWA URL
3. Azure handles HTTPS certificates automatically
