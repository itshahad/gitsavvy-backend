import os

API_URL = "https://api.github.com/"
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN")

def headers():
    if not GITHUB_API_TOKEN:
        return {"Accept": "application/vnd.github+json"}
    else:
        {"Accept": "application/vnd.github+json","Authorization": f"Bearer {GITHUB_API_TOKEN}"}