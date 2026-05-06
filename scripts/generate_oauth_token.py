from __future__ import annotations

import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow

# OAuth only for creating/editing Google Docs and sharing/moving files in Drive.
# Email is sent via SMTP and does not require Google OAuth.
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


def main() -> None:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("Definí GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET antes de ejecutar.")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    print(json.dumps({"refresh_token": creds.refresh_token, "scopes": creds.scopes}, indent=2))


if __name__ == "__main__":
    main()
