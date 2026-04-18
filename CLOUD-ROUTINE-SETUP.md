# Cloud Routine Setup — "Update weekly dashboard"

This moves the daily "Update weekly dashboard" routine off your laptop. Once set up:

- **Every morning** (or when Power Automate nudges it), GitHub Actions will
  download the latest POS files from your OneDrive, invoke Claude to update
  `index.html`, and commit. The existing Azure Static Web Apps workflow then
  auto-deploys.

You need to do four one-time setups:

1. Register an Azure AD app and grant it read access to your OneDrive.
2. Add five secrets to this GitHub repo.
3. (Optional but recommended) Add a GitHub trigger step to your Power Automate flow.
4. Test the workflow manually.

---

## 1. Azure AD app registration (reads OneDrive via Microsoft Graph)

1. Portal → **Entra ID** → **App registrations** → **+ New registration**
   - **Name**: `PE Dashboard Updater`
   - **Supported account types**: Single tenant
   - **Redirect URI**: leave blank
   - Click **Register**.
2. On the new app page, copy:
   - **Application (client) ID** → you'll use this as `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → `AZURE_TENANT_ID`
3. **API permissions** → **+ Add a permission** → **Microsoft Graph** →
   **Application permissions** → search `Files.Read.All` → check it → **Add permissions**.
4. Click **Grant admin consent for <tenant>** (requires an admin; if that's not
   you, send the app's client ID to your IT admin with the request).
5. **Certificates & secrets** → **+ New client secret** →
   - Description: `github-actions`
   - Expiry: 24 months
   - **Copy the Value immediately** → `AZURE_CLIENT_SECRET`.

> **Why `Files.Read.All`?** It's an application-level permission, so the job
> can run unattended without your Microsoft login. It does grant read access
> to every user's OneDrive in the tenant — if your IT team prefers tighter
> scoping, move the POS Daily Files folder to a SharePoint site and use
> `Sites.Selected` instead. Ask if you want that variant.

---

## 2. GitHub repo secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
Add all of these:

| Name                   | Value                                                                 |
| ---------------------- | --------------------------------------------------------------------- |
| `AZURE_TENANT_ID`      | Directory (tenant) ID from step 1                                     |
| `AZURE_CLIENT_ID`      | Application (client) ID from step 1                                   |
| `AZURE_CLIENT_SECRET`  | Client secret value from step 1                                       |
| `ONEDRIVE_USER_EMAIL`  | Your email, e.g. `jz.tan@argilepartners.com`                          |
| `ONEDRIVE_FOLDER_PATH` | `Condor/Project Money/POS Daily/POS Daily Files`                      |
| `ANTHROPIC_API_KEY`    | From console.anthropic.com → API Keys                                 |

---

## 3. Extend Power Automate to trigger the workflow (optional, recommended)

The workflow also runs on a nightly cron (15:30 UTC = 23:30 SGT), so this step
is optional. But triggering from Power Automate means the dashboard updates
within minutes of the last email landing instead of waiting for the next cron.

In your existing flow (the one that saves attachments to OneDrive):

1. After the "Create file" action, add a **Condition**:
   - Check whether all 4 files for today exist in the folder.
   - Easiest approximation: condition on `triggerOutputs()?['body/subject']`
     containing the second restaurant's identifier (so you only fire once per day).
2. In the **If yes** branch, add an **HTTP** action:
   - Method: `POST`
   - URI: `https://api.github.com/repos/tanjz-ap/pe_dashboard_live/actions/workflows/update-dashboard.yml/dispatches`
   - Headers:
     - `Accept`: `application/vnd.github+json`
     - `Authorization`: `Bearer <fine-grained PAT>`
     - `X-GitHub-Api-Version`: `2022-11-28`
     - `User-Agent`: `power-automate`
   - Body: `{"ref": "main"}`

Create the **fine-grained PAT** at github.com → Settings → Developer settings →
Personal access tokens → **Fine-grained tokens**. Scope it to just
`tanjz-ap/pe_dashboard_live` with `Actions: Read and write` permission, and
store it as a secure input variable in Power Automate (not in the HTTP action
body in plain text).

---

## 4. Test it

1. Repo → **Actions** → **Update weekly dashboard** → **Run workflow** → `main`.
2. Watch the logs:
   - "Fetch latest POS files" should print `Report date: YYYY-MM-DD`.
   - "Run Revenue Agent (Claude)" should show Claude editing `index.html`.
   - "Commit and push" should create a commit like
     `Update weekly dashboard — 2026-04-17`.
3. The existing Azure Static Web Apps workflow then auto-deploys the new
   `index.html`. The live dashboard should reflect the update within 2–3 minutes.

### Safe-to-rerun guarantees

- If fewer than 4 files exist for any date, the workflow exits cleanly (no commit).
- If the HEAD commit already references the detected report date, the workflow
  exits cleanly (no commit).
- `concurrency: update-dashboard` prevents two runs from racing if Power
  Automate and the cron fire close together.

---

## Troubleshooting

- **401 from Graph** → secret expired or admin consent wasn't granted. Re-grant
  consent and rotate `AZURE_CLIENT_SECRET`.
- **"No complete day available"** → expected if POS emails haven't all arrived
  yet. The workflow will succeed on the next run.
- **Claude didn't edit `index.html` the way you wanted** → tune the `prompt:`
  block in `.github/workflows/update-dashboard.yml`. Add any domain rules your
  local Revenue Agent uses (e.g. column interpretation, rounding rules).
- **Cost concern** → each run uses one Claude invocation (~$0.50–$2 depending
  on file size). If stable after a few weeks, we can port the logic to a
  deterministic Python script and drop the LLM step.
