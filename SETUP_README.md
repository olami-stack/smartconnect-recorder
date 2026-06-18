# Smart Connect — Automatic Show Recorder (free, GitHub Actions + Google Drive)

This records all five shows automatically on schedule and uploads each to a
public Google Drive folder. No server, no monthly cost. Best-effort: GitHub's
cron can run a few minutes late, which is why each job starts ~3 min early and
records ~35 min.

## What records when (already set in the workflow)

| Station       | Show (WAT)        | Records (UTC)  |
|---------------|-------------------|----------------|
| XL 106.9      | Tue 10:30 AM      | Tue 09:27      |
| Invicta 98.9  | Tue 3:30 PM       | Tue 14:27      |
| Afia 99.3     | Fri 5:00 PM       | Fri 15:57      |
| RR 92.9       | Fri 5:30 PM       | Fri 16:27      |
| RR 107.1      | Fri 6:30 PM       | Fri 17:27      |

---

## ONE-TIME SETUP

### 1. Google Cloud + Drive API
1. Go to console.cloud.google.com → create a project ("smartconnect-recorder").
2. APIs & Services → Library → enable **Google Drive API**.
3. APIs & Services → Credentials → **Create Credentials → Service Account**.
   Name it, click through, Done.
4. Open the service account → **Keys** → Add Key → **JSON** → download it.
   Keep this file safe — it is the robot's password.

### 2. The Drive folder
5. In Google Drive, create a folder e.g. "SmartConnect Recordings".
6. Share it with the service account email (looks like
   `something@your-project.iam.gserviceaccount.com`) as **Editor**.
7. Open the folder; copy the **folder ID** from the URL — the part after
   `/folders/`.
8. (For in-app playback) Right-click the folder → Share → General access →
   **Anyone with the link → Viewer**. Uploaded files are also made public by
   the script automatically.

### 3. Create the API key for the app to LIST files
9. In the same Google Cloud project → Credentials → Create Credentials →
   **API key**. Restrict it to the Drive API. This key goes in the app
   (front-end) to read the public folder listing. (Safe: it can only read
   public files.)

### 4. GitHub repo + Secrets
10. Put these files in a GitHub repo (public repo = unlimited free Actions
    minutes).
11. Repo → Settings → Secrets and variables → Actions → New repository secret.
    Add each of these:

    - `GDRIVE_SERVICE_ACCOUNT_JSON` → paste the ENTIRE contents of the JSON
      key file from step 4.
    - `GDRIVE_FOLDER_ID` → the folder ID from step 7.
    - `STREAM_XL1069`   → https://ice31.securenetsystems.net/XL1069FM
    - `STREAM_INV989`   → https://media2.streambrothers.com:2020/stream/8098
    - `STREAM_AFIA993`  → https://stream.afia993.com/stream
    - `STREAM_RR929`    → https://uk25freenew.listen2myradio.com/live.mp3
    - `STREAM_RR1071`   → (the confirmed Royal Roots 107.1 stream URL)

---

## TEST IT (before waiting for a real show)
- Repo → Actions → "Record Smart Connect Shows" → **Run workflow** →
  pick a station that is currently ON AIR and set minutes = 2.
- After ~3 min, check the Drive folder for the test MP3 and play it to confirm
  there is ACTUAL AUDIO. Do this during broadcast hours — a station that is
  off-air will (correctly) skip the upload.

## NOTES & LIMITS (be honest with Airtel)
- Best-effort, not guaranteed: GitHub cron can fire late; a badly delayed run
  could clip a show open. The early-start buffer covers normal lateness.
- If a stream is off-air/silent at show time, the run skips upload rather than
  saving a junk file (size check in the script).
- ~17 MB per 35-min show × 5/week ≈ 85 MB/month → 15 GB free Drive lasts years.
