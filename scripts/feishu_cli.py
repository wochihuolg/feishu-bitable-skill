#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

FEISHU_BASE = "https://open.feishu.cn"


class HttpError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _http_request(method: str, url: str, *, headers: Optional[Dict[str, str]] = None, data: Optional[bytes] = None, timeout: int = 30) -> Tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        raise HttpError(exc.code, body.decode("utf-8", errors="replace"))


def _http_json(method: str, url: str, *, headers: Optional[Dict[str, str]] = None, body: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Dict[str, Any]:
    data = None
    hdrs = headers or {}
    if body is not None:
        data = _json_dumps(body).encode("utf-8")
        hdrs = {**hdrs, "Content-Type": "application/json; charset=utf-8"}
    status, content = _http_request(method, url, headers=hdrs, data=data, timeout=timeout)
    try:
        return json.loads(content.decode("utf-8"))
    except Exception:
        return {"status_code": status, "text": content.decode("utf-8", errors="replace")}


def _build_multipart(fields: Dict[str, Any], files: Dict[str, Tuple[str, bytes, str]]) -> Tuple[bytes, str]:
    boundary = "----codexboundary%08x" % (os.getpid() & 0xFFFFFFFF)
    body = bytearray()

    def add_line(line: str) -> None:
        body.extend(line.encode("utf-8"))
        body.extend(b"\r\n")

    for name, val in fields.items():
        add_line(f"--{boundary}")
        add_line(f"Content-Disposition: form-data; name=\"{name}\"")
        add_line("")
        add_line(str(val))

    for name, (filename, content, ctype) in files.items():
        add_line(f"--{boundary}")
        add_line(f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"")
        add_line(f"Content-Type: {ctype}")
        add_line("")
        body.extend(content)
        body.extend(b"\r\n")

    add_line(f"--{boundary}--")
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _download_file(url: str) -> Tuple[bytes, Optional[str], Optional[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read()
        ctype = resp.headers.get("Content-Type")
    filename = os.path.basename(urllib.parse.urlparse(url).path)
    filename = urllib.parse.unquote(filename) if filename else None
    return content, ctype, filename


def _guess_filename(filename: Optional[str], ctype: Optional[str]) -> str:
    if filename and "." in filename:
        return filename
    ext = None
    if ctype:
        ext = mimetypes.guess_extension(ctype.split(";", 1)[0].strip())
    if not ext:
        ext = ".bin"
    return (filename or "file") + ext


def _extract_app_token(value: str) -> str:
    s = value.strip()
    if re.fullmatch(r"(?:basc|app)[A-Za-z0-9_-]+", s):
        return s
    m = re.search(r"/base/([A-Za-z0-9_-]+)", s)
    if m:
        return m.group(1)
    m = re.search(r"/bitable/([A-Za-z0-9_-]+)", s)
    if m:
        return m.group(1)
    return s


def _resolve_app_token(value: str, token: str) -> str:
    if "/wiki/" in value:
        wiki_token = value.split("/wiki/", 1)[1].split("?", 1)[0]
        url = f"{FEISHU_BASE}/open-apis/wiki/v2/spaces/get_node?token={wiki_token}"
        resp = _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})
        if isinstance(resp, dict) and resp.get("code") in (0, "0"):
            node = (resp.get("data") or {}).get("node") or {}
            if str(node.get("obj_type")) == "bitable" and node.get("obj_token"):
                return str(node.get("obj_token"))
        raise RuntimeError("wiki link not resolvable to bitable")
    return _extract_app_token(value)


def _get_tenant_token(app_id: str, app_secret: str) -> str:
    url = f"{FEISHU_BASE}/open-apis/auth/v3/tenant_access_token/internal"
    data = _http_json("POST", url, body={"app_id": app_id, "app_secret": app_secret})
    if not isinstance(data, dict) or data.get("code") not in (0, "0"):
        raise RuntimeError(f"tenant_access_token failed: {data}")
    token = data.get("tenant_access_token")
    if not token:
        raise RuntimeError(f"tenant_access_token missing: {data}")
    return token


def _load_dotenv() -> None:
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if key and key not in os.environ:
                    os.environ[key] = val
    except FileNotFoundError:
        return


def _load_json_arg(value: Optional[str], path: Optional[str]) -> Optional[Any]:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    if value:
        return json.loads(value)
    return None


def _auth_token(args: argparse.Namespace) -> str:
    if args.tenant_token:
        return args.tenant_token
    _load_dotenv()
    app_id = args.app_id or os.getenv("FEISHU_APP_ID", "")
    app_secret = args.app_secret or os.getenv("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise RuntimeError("app_id/app_secret required")
    return _get_tenant_token(app_id, app_secret)


def cmd_create_app(args: argparse.Namespace) -> None:
    token = _auth_token(args)
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps"
    resp = _http_json("POST", url, headers={"Authorization": f"Bearer {token}"}, body={"name": args.name})
    print(_json_dumps(resp))


def cmd_list_tables(args: argparse.Namespace) -> None:
    token = _auth_token(args)
    app_token = _resolve_app_token(args.app_token, token)
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables"
    resp = _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})
    print(_json_dumps(resp))


def cmd_create_table(args: argparse.Namespace) -> None:
    token = _auth_token(args)
    app_token = _resolve_app_token(args.app_token, token)
    fields = _load_json_arg(args.fields, args.fields_file) or []
    body = {
        "table": {
            "name": args.name,
            "default_view_name": args.default_view_name or "Table View",
            "fields": fields,
        }
    }
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables"
    resp = _http_json("POST", url, headers={"Authorization": f"Bearer {token}"}, body=body)
    print(_json_dumps(resp))


def cmd_create_record(args: argparse.Namespace) -> None:
    token = _auth_token(args)
    app_token = _resolve_app_token(args.app_token, token)
    fields = _load_json_arg(args.fields, args.fields_file) or {}
    body = {"fields": fields, "field_key": args.field_key}
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables/{args.table_id}/records"
    resp = _http_json("POST", url, headers={"Authorization": f"Bearer {token}"}, body=body)
    print(_json_dumps(resp))


def cmd_upload_attachment(args: argparse.Namespace) -> None:
    token = _auth_token(args)
    app_token = _resolve_app_token(args.app_token, token)

    content, ctype, fname = _download_file(args.file_url)
    fname = _guess_filename(fname, ctype)
    ctype = ctype.split(";", 1)[0].strip() if ctype else "application/octet-stream"
    parent_type = "bitable_image" if ctype.startswith("image/") else "bitable_file"

    fields = {
        "file_name": fname,
        "parent_type": parent_type,
        "parent_node": app_token,
        "size": str(len(content)),
    }
    files = {"file": (fname, content, ctype)}
    body, content_type = _build_multipart(fields, files)
    url = f"{FEISHU_BASE}/open-apis/drive/v1/medias/upload_all"
    status, resp_bytes = _http_request("POST", url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }, data=body, timeout=120)
    resp = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {"status_code": status}
    if resp.get("code") not in (0, "0"):
        print(_json_dumps(resp))
        return
    file_token = (resp.get("data") or {}).get("file_token")
    if not file_token:
        print(_json_dumps(resp))
        return

    update_body = {"fields": {args.field_name: [{"file_token": file_token}]}}
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables/{args.table_id}/records/{args.record_id}"
    resp2 = _http_json("PUT", url, headers={"Authorization": f"Bearer {token}"}, body=update_body)
    print(_json_dumps(resp2))


def cmd_create_docx(args: argparse.Namespace) -> None:
    token = _auth_token(args)
    url = f"{FEISHU_BASE}/open-apis/docx/v1/documents"
    resp = _http_json("POST", url, headers={"Authorization": f"Bearer {token}"}, body={"title": args.title})
    print(_json_dumps(resp))


def cmd_list_docx_blocks(args: argparse.Namespace) -> None:
    token = _auth_token(args)
    url = f"{FEISHU_BASE}/open-apis/docx/v1/documents/{args.document_id}/blocks"
    resp = _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})
    print(_json_dumps(resp))


def main() -> None:
    parser = argparse.ArgumentParser(description="Feishu Bitable CLI")
    parser.add_argument("--app-id")
    parser.add_argument("--app-secret")
    parser.add_argument("--tenant-token")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create-app")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_create_app)

    p = sub.add_parser("list-tables")
    p.add_argument("--app-token", required=True)
    p.set_defaults(func=cmd_list_tables)

    p = sub.add_parser("create-table")
    p.add_argument("--app-token", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--default-view-name")
    p.add_argument("--fields")
    p.add_argument("--fields-file")
    p.set_defaults(func=cmd_create_table)

    p = sub.add_parser("create-record")
    p.add_argument("--app-token", required=True)
    p.add_argument("--table-id", required=True)
    p.add_argument("--field-key", default="name")
    p.add_argument("--fields")
    p.add_argument("--fields-file")
    p.set_defaults(func=cmd_create_record)

    p = sub.add_parser("upload-attachment")
    p.add_argument("--app-token", required=True)
    p.add_argument("--table-id", required=True)
    p.add_argument("--record-id", required=True)
    p.add_argument("--field-name", required=True)
    p.add_argument("--file-url", required=True)
    p.set_defaults(func=cmd_upload_attachment)

    p = sub.add_parser("create-docx")
    p.add_argument("--title", required=True)
    p.set_defaults(func=cmd_create_docx)

    p = sub.add_parser("list-docx-blocks")
    p.add_argument("--document-id", required=True)
    p.set_defaults(func=cmd_list_docx_blocks)

    args = parser.parse_args()
    try:
        args.func(args)
    except HttpError as exc:
        print(_json_dumps({"error": str(exc), "status": exc.status, "body": exc.body}))
        sys.exit(2)
    except Exception as exc:
        print(_json_dumps({"error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
