import os
import requests
import subprocess
import json
import time
from sharepoint_token import get_access_token
from dotenv import load_dotenv

load_dotenv()

SITE_HOST = "jmangroupltd.sharepoint.com"
SITE_NAME = "AllHands"
FOLDER_PATH = "Documents/CoE/DS&AI/JHire/Resume"
UPLOAD_URL = "http://localhost:3000/api/extractResumeDetails"

processed_files = set()

def get_site_id(token):
    url = f"https://graph.microsoft.com/v1.0/sites?search={SITE_NAME}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    print("🔎 Site Search Response:", resp.status_code, resp.text[:300])

    sites = resp.json().get("value", [])
    for s in sites:
        if SITE_NAME.lower() in s["name"].lower():
            print(f" Found Site: {s['name']} ({s['id']})")
            return s["id"]
    return None


def get_drive_id(token, site_id):
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    print(" Drive Response:", resp.status_code, resp.text[:300])

    drives = resp.json().get("value", [])
    for d in drives:
        print(f" Drive Found: {d['name']} → {d['id']}")
        if d["name"].lower() == "documents":  # case-insensitive
            return d["id"]
    return drives[0]["id"] if drives else None


def list_pdfs(token, site_id, drive_id):
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{FOLDER_PATH}:/children"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    print("🔍 Request URL:", url)
    print("🔍 Response status:", resp.status_code)
    print("🔍 Raw response:", resp.text[:300])  # print first 300 characters

    return [f for f in resp.json().get("value", []) if f["name"].lower().endswith(".pdf")]

def download_pdf(token, download_url):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(download_url, headers=headers)
    return resp.content if resp.status_code == 200 else None

def extract_resume(pdf_bytes):
    process = subprocess.Popen(
        ["python", "scripts/extract_Resume.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate(input=pdf_bytes)
    if stderr:
        print(" Extraction error:", stderr.decode())
    return json.loads(stdout.decode())

def upload_resume(data, file_bytes, filename):
    print(" Calling list_pdfs()...")

    try:
        files = list_pdfs(token, site_id, drive_id)
        print(f" Found {len(files)} PDF(s)")
        for f in files:
            print("📄", f["name"])
    except Exception as e:
        print(f" Error while listing PDFs: {e}")
        return

    metadata = {
        "college": "Auto",
        "exam_date": "2025-08-01T10:00",
        "expiry_date": "2025-08-10T10:00"
    }
    metadata.update(data)
    response = requests.post(UPLOAD_URL, data=metadata, files=files)
    print(f" Uploaded {filename}: {response.status_code}")

def poll_loop(interval_sec=60):
    print(" Getting access token...")
    token = get_access_token()
    site_id = get_site_id(token)
    drive_id = get_drive_id(token, site_id)

    while True:
        try:
            print("\n Checking for new resumes...")
            files = list_pdfs(token, site_id, drive_id)

            for file in files:
                filename = file["name"]
                if filename in processed_files:
                    continue

                download_url = file["@microsoft.graph.downloadUrl"]
                print(f" Downloading new file: {filename}")
                pdf_bytes = download_pdf(token, download_url)

                if not pdf_bytes:
                    print(f" Failed to download {filename}")
                    continue

                print(f" Extracting {filename}...")
                result = extract_resume(pdf_bytes)
                print(f" Data: {result}")

                print(f" Uploading {filename}...")
                upload_resume(result, pdf_bytes, filename)
                processed_files.add(filename)

            time.sleep(interval_sec)

        except Exception as e:
            print(f" Error in poll loop: {e}")
            time.sleep(interval_sec)

if __name__ == "__main__":
    poll_loop(interval_sec=60)  # check every 60 seconds
