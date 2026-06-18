#!/usr/bin/env python3
"""Record a live radio stream with ffmpeg and upload to Google Drive using
OAuth user credentials (your own account's 15GB quota)."""

import argparse
import datetime
import os
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

STATIONS = {
    "xl1069":  {"name": "XL 106.9 FM",         "env": "STREAM_XL1069"},
    "inv989":  {"name": "Invicta 98.9 FM",     "env": "STREAM_INV989"},
    "afia993": {"name": "Afia 99.3 FM",        "env": "STREAM_AFIA993"},
    "rr929":   {"name": "Royal Roots 92.9 FM", "env": "STREAM_RR929"},
    "rr1071":  {"name": "Royal Roots 107.1 FM","env": "STREAM_RR1071"},
}

MIN_VALID_BYTES = 200 * 1024
TOKEN_URI = "https://oauth2.googleapis.com/token"


def record(stream_url, minutes, out_path):
    duration_secs = int(float(minutes) * 60)
    cmd = [
        "ffmpeg", "-y", "-i", stream_url, "-t", str(duration_secs),
        "-acodec", "libmp3lame", "-b:a", "128k",
        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10",
        out_path,
    ]
    print(f"[ffmpeg] recording {duration_secs}s from stream...")
    try:
        subprocess.run(cmd, timeout=duration_secs + 60, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except subprocess.TimeoutExpired:
        print("[ffmpeg] hit timeout guard.")
    return os.path.exists(out_path)


def upload_to_drive(file_path, file_name, folder_id):
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GDRIVE_REFRESH_TOKEN"],
        client_id=os.environ["GDRIVE_CLIENT_ID"],
        client_secret=os.environ["GDRIVE_CLIENT_SECRET"],
        token_uri=TOKEN_URI,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    service = build("drive", "v3", credentials=creds)
    metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(file_path, mimetype="audio/mpeg", resumable=True)
    created = service.files().create(body=metadata, media_body=media, fields="id").execute()
    file_id = created["id"]
    service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()
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

    now = datetime.datetime.now(ZoneInfo("Africa/Lagos"))
    stamp = now.strftime("%Y-%m-%d_%H%M")
    safe_name = station["name"].replace(" ", "_").replace(".", "")
    file_name = f"SmartConnect_{safe_name}_{stamp}_WAT.mp3"

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, file_name)
        if not record(stream_url, args.minutes, out_path):
            print("[skip] no file (stream unreachable). Not uploading.")
            sys.exit(0)
        size = os.path.getsize(out_path)
        print(f"[check] recorded {size/1024:.0f} KB")
        if size < MIN_VALID_BYTES:
            print(f"[skip] under {MIN_VALID_BYTES/1024:.0f}KB — likely off-air/silent. Not uploading.")
            sys.exit(0)
        upload_to_drive(out_path, file_name, os.environ["GDRIVE_FOLDER_ID"])
    print("[done]")


if __name__ == "__main__":
    main()
