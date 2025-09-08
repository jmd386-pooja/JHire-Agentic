from msal import ConfidentialClientApplication
import os
from dotenv import load_dotenv

load_dotenv()
TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://graph.microsoft.com/.default"]

def get_access_token():
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(scopes=SCOPE)

    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Token acquisition failed: {result}")

if __name__ == "__main__":
    try:
        token = get_access_token()
        print("✅ Access token acquired successfully!")
        print(token[:100] + "...")  # Show only the first part of the token
    except Exception as e:
        print(f"❌ Failed to get token: {e}")   
