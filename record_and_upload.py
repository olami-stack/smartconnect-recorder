#!/usr/bin/env python3
"""
Record a live radio stream with ffmpeg and upload it to a public Google Drive
folder via a service account. Designed to run inside GitHub Actions.

Validates the recording before upload: if ffmpeg failed or the file is
suspiciously small (stream was off-air / silent), it logs and exits WITHOUT
uploading a junk file.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Friendly names + the env var holding each stream URL.
STATIONS = {
    "xl1069":  {"name": "XL 106.9 FM",        "env": "STREAM_XL1069"},
    "inv989":  {"name": "Invicta 98.9 FM",    "env": "STREAM_INV989"},
    "afia993": {"name": "Afia 99.3 FM",       "env": "STREAM_AFIA993"},
    "rr929":   {"name": "Royal Roots 92.9 FM","env": "STREAM_RR929"},
    "rr1071":  {"name": "Royal Roots 107.1 FM","env": "STREAM_RR1071"},
}

# Below this size we assume the stream was off-air / silent and skip upload.
# ~64kbps MP3 is ~8KB/sec, so even 1 real minute is ~480KB. 200KB is a safe floor.
MIN_VALID_BYTES = 200 * 1024


def record(stream_url: str, minutes: float, out_path: str) -> bool:
    """Record the stream to MP3. Returns True if ffmpeg produced a file."""
    duration_secs = int(float(minutes) * 60)
    cmd = [
        "ffmpeg", "-y",
        "-i", stream_url,
        "-t", str(duration_secs),
        "-acodec", "libmp3lame",
        "-b:a", "128k",
        "-reconnect", "1",            # auto-reconnect if the stream blips
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "10",
        out_path,
    ]
    print(f"[ffmpeg] recording {duration_secs}s from stream...")
    # ffmpeg gets the full duration + 60s grace before we force-kill it.
    try:
        subprocess.run(cmd, timeout=duration_secs + 60, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except subprocess.TimeoutExpired:
        print("[ffmpeg] hit timeout guard (expected if stream never closed).")
    return os.path.exists(out_path)


def upload_to_drive(file_path: str, file_name: str, folder_id: str, creds_json: str):
    """Upload the file to the Drive folder and make it readable by anyone."""
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds)

    metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(file_path, mimetype="audio/mpeg", resumable=True)
    created = service.files().create(
        body=metadata, media_body=media, fields="id"
    ).execute()
    file_id = created["id"]

    # Make it public-readable so the app can list & stream it without auth.
    service.permissions().create(
        fileId=file_id, body={"role": "reader", "type": "anyone"}
    ).execute()

    print(f"[drive] uploaded: {file_name} (id={file_id})")
    return file_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--station", required=True, choices=list(STATIONS.keys()))
    ap.add_argument("--minutes", required=True)
    args = ap.parse_args()

    station = STATIONS[args.station]
    stream_url = os.environ.get(station["env"], "").strip()
    if not stream_url:
        print(f"[error] No stream URL set for {args.station} ({station['env']}).")
        sys.exit(1)

    # Timestamp in WAT so filenames read in local Nigerian time.
    now = datetime.datetime.now(ZoneInfo("Africa/Lagos"))
    stamp = now.strftime("%Y-%m-%d_%H%M")
    safe_name = station["name"].replace(" ", "_").replace(".", "")
    file_name = f"SmartConnect_{safe_name}_{stamp}_WAT.mp3"

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, file_name)

        ok = record(stream_url, args.minutes, out_path)
        if not ok:
            print("[skip] ffmpeg produced no file (stream unreachable). Not uploading.")
            sys.exit(0)  # exit 0 so a normal off-air night isn't a 'failed' run

        size = os.path.getsize(out_path)
        print(f"[check] recorded {size/1024:.0f} KB")
        if size < MIN_VALID_BYTES:
            print(f"[skip] file under {MIN_VALID_BYTES/1024:.0f}KB — likely off-air/silent. Not uploading.")
            sys.exit(0)

        creds_json = os.environ["GDRIVE_SERVICE_ACCOUNT_JSON"]
        folder_id = os.environ["GDRIVE_FOLDER_ID"]
        upload_to_drive(out_path, file_name, folder_id, creds_json)

    print("[done]")


if __name__ == "__main__":
    main()
