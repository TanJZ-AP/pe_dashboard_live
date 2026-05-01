# Cloud Routine Setup — KEK "Update weekly dashboard"

Moves the daily KEK dashboard refresh off Solomon's laptop. Once set up:

- Every evening (22:45 SGT cron, or sooner if Power Automate triggers), GitHub Actions
  syncs new POS files from OneDrive into `pos_inbox/`, runs the deterministic Python
  pipeline (`refresh_dashboard.py`), commits the updated `index.html` + parsed JSON +
  POS files, and the connected Azure Static Web App auto-deploys.

Unlike the PE dashboard, **KEK's pipeline is fully deterministic — no Claude/LLM call
in the daily loop**. Costs are essentially $0 per run.

You need to do **five** one-time setups:

1. Reuse the existing `PE Dashboard Updater` AAD app for OneDrive reads (no new app needed).
2. Bootstrap `pos_inbox/` and `historical/` with starting POS files.
3. Add six secrets to the GitHub repo.
4. (Optional) Add a GitHub trigger step to a Power Automate flow.
5. Test the workflow manually.

---

## 1. Reuse `PE Dashboard Updater` AAD app

The existing PE app already has `Files.Read.All` (application-level) — it can read
the KEK files in OneDrive without a new registration. Just copy its 3 secrets to
the new repo (next step).

If you'd rather create a separate `KEK Dashboard Updater` app for cleaner audit
attribution and independent secret rotation, follow the same registration steps as
the PE setup — single-tenant, `Files.Read.All` application permission, admin consent,
new client secret — and use those values instead.

---

## 2. Bootstrap `pos_inbox/` and `historical/`

The cloud workflow only fetches per-day individual POS files going forward. The
historical batch files (DayPartGroup, OrderType, weekly dailyReport summaries —
covering Mar 30–Apr 15 dates that pre-date the per-day file format) need to be
in the repo as a frozen snapshot before the first workflow run.

On your laptop, with the new repo cloned:

```bash
cd kek_dashboard_live
mkdir -p pos_inbox historical

# From your OneDrive sync of "Condor Folder/Keng Eng Kee/Daily POS Reports/":
#
# 1. Copy any per-day individual files into pos_inbox/. These match the patterns:
#      <Outlet>_dailyReport_YYYY-MM-DD.xlsx
#      <Outlet>_menuItemReport_YYYY-MM-DD.xlsx
#    where <Outlet> is one of:
#      "Keng Eng Kee Seafood @ Alexandra Village"
#      "Keng Eng Kee Seafood @ Punggol SAFRA"
#      "Tampines Safra KEK"
#      "Wok In Burger Pte Ltd"
#
# 2. Copy historical batch files into historical/. These are everything else:
#      DayPartGroup_<mmdd>~<mmdd>_*.xlsx
#      OrderTypeReport_<dates>_*.xlsx
#      DayPartReport_<dates>_*.xlsx
#      dailyReport_YYYY.MM.DD~YYYY.MM.DD_*.xlsx (weekly summaries with dot-dates)

git add pos_inbox/ historical/
git commit -m "Bootstrap POS files (pos_inbox + historical snapshot)"
git push origin main
```

After this one-time bootstrap, `historical/` is frozen — nothing in the daily
workflow ever modifies it. `pos_inbox/` grows over time as new days arrive.

---

## 3. GitHub repo secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

| Name                                       | Value                                                                |
| ------------------------------------------ | -------------------------------------------------------------------- |
| `AZURE_TENANT_ID`                          | Same as PE (Directory tenant ID)                                     |
| `AZURE_CLIENT_ID`                          | Same as PE (PE Dashboard Updater app)                                |
| `AZURE_CLIENT_SECRET`                      | Same as PE                                                           |
| `ONEDRIVE_USER_EMAIL`                      | The email that owns the SharePoint folder, e.g. `st@argilepartners.com` |
| `ONEDRIVE_FOLDER_PATH`                     | `Condor Folder/Keng Eng Kee/Daily POS Reports`                       |
| `AZURE_STATIC_WEB_APPS_API_TOKEN_KEK`      | From the SWA → Manage deployment token (see DEPLOY-GUIDE.md step 4)  |

---

## 4. Power Automate trigger (optional)

Same pattern as PE. After the "Create file" action that saves attachments to OneDrive,
add a Condition that fires once per day (e.g. when the last expected outlet's file lands),
then an HTTP POST to:

```
https://api.github.com/repos/tanjz-ap/kek_dashboard_live/actions/workflows/update-dashboard.yml/dispatches
```

with `Authorization: Bearer <fine-grained PAT>` (scoped to this repo, `Actions: Read and write`)
and body `{"ref": "main"}`. Store the PAT as a Power Automate secure variable.

The 22:45 SGT cron runs in any case.

---

## 5. Test it

1. Repo → **Actions** → **Update KEK dashboard** → **Run workflow** → `main`.
2. Watch the logs:
   - **Fetch latest POS files** should print `Report date: YYYY-MM-DD` and "Synced N new file(s) to pos_inbox/" on the first run.
   - **Run KEK pipeline** should show all 5 steps of `refresh_dashboard.py` succeed and end with "JS OK".
   - **Commit and push** should create `Update KEK dashboard — YYYY-MM-DD`.
3. The connected Azure Static Web App workflow auto-deploys on the new commit.
   The live dashboard reflects the update within 2–3 minutes.

### Safe-to-rerun guarantees

- `fetch_pos_files.py` only downloads files not already in `pos_inbox/`.
- `pull_latest.py` skips dates already present in `kek_parsed.json`.
- If HEAD commit already covers the detected date (subject line match), the workflow exits cleanly without committing.
- `concurrency: update-dashboard` prevents two runs from racing.

---

## Troubleshooting

- **401 from Graph** → secret expired or admin consent not granted. Re-grant on the AAD app and rotate `AZURE_CLIENT_SECRET`.
- **"No complete day (8 files) available yet"** → expected when only some of the 4 outlets' POS emails have landed. Cron will succeed on the next run.
- **Pipeline ends with "JS ERROR"** → the inline DATA block produced something the dashboard JS doesn't accept. Most often a schema regression after a script edit. Roll back the offending script change or re-run with `python -X tracemalloc` for hints.
- **Week tabs (W1-W5) showing wrong dates** → check `KEK_REPORT_MONTH` is unset (auto-derives from today). For monthly close, you can pin via repo variable: `KEK_REPORT_MONTH=2026-04` to lock the workflow to a closed month.
- **Historical view (W1/W2 etc.) is missing top items** → confirm `historical/` was bootstrapped and committed; the workflow won't refetch it.
