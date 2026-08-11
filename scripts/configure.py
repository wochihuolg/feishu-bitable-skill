#!/usr/bin/env python3
import argparse
import getpass
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = SKILL_DIR / ".env"
TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def save_env(app_id: str, app_secret: str) -> None:
    content = f"FEISHU_APP_ID={app_id}\nFEISHU_APP_SECRET={app_secret}\n"
    fd = os.open(ENV_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
    finally:
        os.chmod(ENV_PATH, 0o600)


def check(app_id: str, app_secret: str) -> None:
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Feishu verification failed with HTTP {exc.code}") from exc
    if data.get("code") not in (0, "0") or not data.get("tenant_access_token"):
        raise RuntimeError(f"Feishu rejected the credentials (code={data.get('code')})")
    print("Credentials verified. The access token was not displayed or stored.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure Feishu credentials securely")
    parser.add_argument("--check", action="store_true", help="verify the saved credentials")
    args = parser.parse_args()

    current = load_env()
    if args.check:
        app_id = current.get("FEISHU_APP_ID", "")
        app_secret = current.get("FEISHU_APP_SECRET", "")
        if not app_id or not app_secret:
            raise RuntimeError("No complete .env found. Run this script without --check first.")
        check(app_id, app_secret)
        return

    default_id = current.get("FEISHU_APP_ID", "")
    prompt = f"Feishu App ID [{default_id}]: " if default_id else "Feishu App ID: "
    app_id = input(prompt).strip() or default_id
    app_secret = getpass.getpass("Feishu App Secret (hidden): ").strip()
    if not app_secret:
        app_secret = current.get("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise RuntimeError("Both App ID and App Secret are required")
    if "\n" in app_id or "\n" in app_secret:
        raise RuntimeError("Credentials must not contain newlines")
    save_env(app_id, app_secret)
    print(f"Credentials saved to {ENV_PATH} with file mode 0600.")
    print("Run: python3 scripts/configure.py --check")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
