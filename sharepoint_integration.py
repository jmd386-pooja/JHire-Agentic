import os
import requests
from dotenv import load_dotenv
from typing import List


load_dotenv()

TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
SHAREPOINT_HOST = os.getenv("SHAREPOINT_HOST")
SHAREPOINT_SITE_NAME = os.getenv("SHAREPOINT_SITE_NAME")
SHAREPOINT_DRIVE_NAME = os.getenv("SHAREPOINT_DRIVE_NAME")
RESUME_FOLDER_ID = os.getenv("RESUME_FOLDER_ID")

def get_graph_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }
    response = requests.post(url, headers=headers, data=data)

    # Add this block to print the response content before raising an error
    if response.status_code != 200:
        print("Error getting token:")
        print("Status Code:", response.status_code)
        print("Response:", response.text)
        response.raise_for_status()

    return response.json()["access_token"]

def fetch_site_and_drive_id(token):
    # Fetch Site ID
    site_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_HOST}:/sites/{SHAREPOINT_SITE_NAME}"
    headers = {"Authorization": f"Bearer {token}"}
    site_res = requests.get(site_url, headers=headers)
    site_res.raise_for_status()
    site_id = site_res.json()["id"]

    # Fetch Drive ID
    drive_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    drive_res = requests.get(drive_url, headers=headers)
    drive_res.raise_for_status()
    drives = drive_res.json()["value"]
    drive_id = next((d["id"] for d in drives if d["name"] == SHAREPOINT_DRIVE_NAME), None)

    return site_id, drive_id

def fetch_pdf_files(drive_id, token):
    folder_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{RESUME_FOLDER_ID}/children"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(folder_url, headers=headers)
    res.raise_for_status()
    items = res.json()["value"]
    pdf_files = [file for file in items if file["name"].lower().endswith(".pdf")]
    return pdf_files

def get_pdf_files_from_sharepoint() -> List[dict]:
    token = get_graph_token()
    site_id, drive_id = fetch_site_and_drive_id(token)
    pdf_files = fetch_pdf_files(drive_id, token)
    return pdf_files


def main():
    token = get_graph_token()
    site_id, drive_id = fetch_site_and_drive_id(token)
    pdf_files = fetch_pdf_files(drive_id, token)

    print(f"Found {len(pdf_files)} PDF resumes:")
    for file in pdf_files:
        print(f"→ {file['name']}")
        print(f"   Download URL: {file.get('@microsoft.graph.downloadUrl')}")

if __name__ == "__main__":
    main()
