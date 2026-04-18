from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen


def parse_google_sheet_id(sheet_url_or_id: str) -> str:
    candidate = sheet_url_or_id.strip()
    if "/spreadsheets/d/" not in candidate:
        return candidate
    parsed = urlparse(candidate)
    parts = parsed.path.split("/")
    if "d" in parts:
        idx = parts.index("d")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    raise ValueError("could not parse google sheet id")


def parse_google_sheet_gid(sheet_url: str) -> str | None:
    parsed = urlparse(sheet_url)
    qs = parse_qs(parsed.fragment)
    gid = qs.get("gid")
    if gid:
        return gid[0]
    if "gid=" in parsed.fragment:
        return parsed.fragment.split("gid=")[-1].split("&")[0]
    return None


def download_google_sheet_xlsx(*, sheet_url_or_id: str, output_path: str | Path) -> Path:
    sheet_id = parse_google_sheet_id(sheet_url_or_id)
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    path = Path(output_path)
    with urlopen(export_url, timeout=15) as response:
        content = response.read()
    path.write_bytes(content)
    return path
