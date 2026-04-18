"""Download the most recent complete day of POS files from OneDrive via Microsoft Graph.

Expects these environment variables:
  AZURE_TENANT_ID
  AZURE_CLIENT_ID
  AZURE_CLIENT_SECRET
  ONEDRIVE_USER_EMAIL   e.g. jz.tan@argilepartners.com
  ONEDRIVE_FOLDER_PATH  e.g. Condor/Project Money/POS Daily/POS Daily Files

Writes files into ./pos_inbox/ and prints the detected report date (YYYY-MM-DD) on the
last stdout line. Exits 0 if downloaded, 2 if no complete day is available yet.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import msal
import requests

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
RESTAURANTS = ("Duo Galleria", "Star Vista")
REPORT_TYPES = ("dailyReport", "menuItemReport")
FILENAME_RE = re.compile(
    r"^PE @ (?P<restaurant>Duo Galleria|Star Vista)_"
    r"(?P<report>dailyReport|menuItemReport)_"
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


def most_recent_complete_date(items: list[dict]) -> tuple[str, dict[tuple[str, str], dict]] | None:
    by_date: dict[str, dict[tuple[str, str], dict]] = {}
    for item in items:
        m = FILENAME_RE.match(item.get("name", ""))
        if not m:
            continue
        key = (m["restaurant"], m["report"])
        by_date.setdefault(m["date"], {})[key] = item

    expected_keys = {(r, t) for r in RESTAURANTS for t in REPORT_TYPES}
    for date in sorted(by_date, reverse=True):
        if set(by_date[date]) >= expected_keys:
            return date, by_date[date]
    return None


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
    result = most_recent_complete_date(items)
    if result is None:
        print("No complete day (4 files) available yet.", file=sys.stderr)
        return 2

    date, files = result
    out_dir = Path("pos_inbox")
    out_dir.mkdir(exist_ok=True)
    for (restaurant, report), item in sorted(files.items()):
        dest = out_dir / item["name"]
        print(f"Downloading {item['name']}", file=sys.stderr)
        download(token, item, dest)

    print(date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
