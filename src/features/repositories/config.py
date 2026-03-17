import os

API_URL = "https://api.github.com/"
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN")


def headers(custom_token: str | None = None):
    # return {"Accept": "application/vnd.github+json"}
    if not GITHUB_API_TOKEN and not custom_token:
        return {"Accept": "application/vnd.github+json"}
    else:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"token {custom_token if custom_token is not None else GITHUB_API_TOKEN}",
        }
