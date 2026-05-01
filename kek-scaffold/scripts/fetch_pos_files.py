"""Sync KEK POS files from OneDrive into ./pos_inbox/ via Microsoft Graph.

Expects these environment variables:
  AZURE_TENANT_ID
  AZURE_CLIENT_ID
  AZURE_CLIENT_SECRET
  ONEDRIVE_USER_EMAIL   e.g. st@argilepartners.com
  ONEDRIVE_FOLDER_PATH  e.g. Condor Folder/Keng Eng Kee/Daily POS Reports

Downloads any individual per-day dailyReport / menuItemReport files
not already present locally, then prints the most recent "complete"
date (where all 4 outlets × 2 report types are present) on the last
stdout line. Exits 0 if at least one complete day exists, 2 otherwise.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import msal
import requests

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
OUTLETS = (
    "Keng Eng Kee Seafood @ Alexandra Village",
    "Keng Eng Kee Seafood @ Punggol SAFRA",
    "Tampines Safra KEK",
    "Wok In Burger Pte Ltd",
)
REPORT_TYPES = ("dailyReport", "menuItemReport")
FILENAME_RE = re.compile(
    r"^(?P<outlet>"
    + "|".join(re.escape(o) for o in OUTLETS)
    + r")_(?P<report>dailyReport|menuItemReport)_(?P<date>\d{4}-\d{2}-\d{2})\.xlsx$"
)


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def acquire_token() -> str:
    app = msal.ConfidentialClientApplication(
        client_id=env("AZURE_CLIENT_ID"),
        authority=f"https://login.microsoftonline.com/{env('AZURE_TENANT_ID')}",
        client_credential=env("AZURE_CLIENT_SECRET"),
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        print(f"Token acquisition failed: {result}", file=sys.stderr)
        sys.exit(1)
    return result["access_token"]


def list_folder(token: str, user: str, folder_path: str) -> list[dict]:
    url = f"{GRAPH_ROOT}/users/{user}/drive/root:/{folder_path}:/children?$top=200"
    items: list[dict] = []
    while url:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
    return items


def download(token: str, item: dict, dest: Path) -> None:
    url = item["@microsoft.graph.downloadUrl"]
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                fh.write(chunk)


def main() -> int:
    token = acquire_token()
    user = env("ONEDRIVE_USER_EMAIL")
    folder = env("ONEDRIVE_FOLDER_PATH")

    items = list_folder(token, user, folder)

    by_date: dict[str, dict[tuple[str, str], dict]] = {}
    individual: list[dict] = []
    for item in items:
        m = FILENAME_RE.match(item.get("name", ""))
        if not m:
            continue
        individual.append(item)
        by_date.setdefault(m["date"], {})[(m["outlet"], m["report"])] = item

    out_dir = Path("pos_inbox")
    out_dir.mkdir(exist_ok=True)

    new_count = 0
    for item in individual:
        dest = out_dir / item["name"]
        if dest.exists():
            continue
        print(f"Downloading {item['name']}", file=sys.stderr)
        download(token, item, dest)
        new_count += 1

    expected = {(o, r) for o in OUTLETS for r in REPORT_TYPES}
    latest_complete = None
    for date in sorted(by_date, reverse=True):
        if set(by_date[date]) >= expected:
            latest_complete = date
            break

    print(f"Synced {new_count} new file(s) to pos_inbox/", file=sys.stderr)
    if not latest_complete:
        print("No complete day (8 files) available yet.", file=sys.stderr)
        return 2

    print(latest_complete)
    return 0


if __name__ == "__main__":
    sys.exit(main())
