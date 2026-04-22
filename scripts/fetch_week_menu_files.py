"""Download menuItemReport xlsx files for one or more historical weeks.

For each Monday (ISO date) passed as a positional argument, downloads the 14
menuItemReport files (7 days x 2 restaurants) into ./pos_inbox/{monday}/.

Expects env: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET,
             ONEDRIVE_USER_EMAIL, ONEDRIVE_FOLDER_PATH.

Usage: python fetch_week_menu_files.py 2026-03-30 2026-04-06
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import msal
import requests

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
RESTAURANTS = ("Duo Galleria", "Star Vista")
FILENAME_RE = re.compile(
    r"^PE @ (?P<restaurant>Duo Galleria|Star Vista)_menuItemReport_"
    r"(?P<date>\d{4}-\d{2}-\d{2})\.xlsx$"
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


def week_dates(monday_iso: str) -> list[str]:
    d0 = date.fromisoformat(monday_iso)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(7)]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: fetch_week_menu_files.py MONDAY_ISO [MONDAY_ISO ...]", file=sys.stderr)
        return 1
    mondays = sys.argv[1:]

    token = acquire_token()
    user = env("ONEDRIVE_USER_EMAIL")
    folder = env("ONEDRIVE_FOLDER_PATH")

    items = list_folder(token, user, folder)
    index: dict[tuple[str, str], dict] = {}
    for item in items:
        m = FILENAME_RE.match(item.get("name", ""))
        if m:
            index[(m["date"], m["restaurant"])] = item

    any_empty = False
    for monday in mondays:
        dates = week_dates(monday)
        out = Path("pos_inbox") / monday
        out.mkdir(parents=True, exist_ok=True)
        got = 0
        for d in dates:
            for r in RESTAURANTS:
                item = index.get((d, r))
                if item is not None:
                    download(token, item, out / item["name"])
                    got += 1
                else:
                    print(f"  missing: PE @ {r}_menuItemReport_{d}.xlsx", file=sys.stderr)
        print(f"{monday}: downloaded {got}/14 files", file=sys.stderr)
        if got == 0:
            any_empty = True

    return 2 if any_empty else 0


if __name__ == "__main__":
    sys.exit(main())
