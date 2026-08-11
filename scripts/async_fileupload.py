#!/usr/bin/env python3
import argparse
import asyncio
import json
import mimetypes
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

FEISHU_BASE = "https://open.feishu.cn"


@dataclass
class Task:
    record_id: str
    file_url: str
    status: str = "queued"
    error: Optional[str] = None
    file_token: Optional[str] = None


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _http_request(method: str, url: str, *, headers: Optional[Dict[str, str]] = None, data: Optional[bytes] = None, timeout: int = 30) -> Tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.getcode(), resp.read()


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


def _auth_token(app_id: Optional[str], app_secret: Optional[str], tenant_token: Optional[str]) -> str:
    if tenant_token:
        return tenant_token
    _load_dotenv()
    aid = app_id or os.getenv("FEISHU_APP_ID", "")
    sec = app_secret or os.getenv("FEISHU_APP_SECRET", "")
    if not aid or not sec:
        raise RuntimeError("app_id/app_secret required")
    return _get_tenant_token(aid, sec)


def _list_tables(token: str, app_token: str) -> List[Dict[str, Any]]:
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables"
    data = _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})
    return (data.get("data") or {}).get("items") or []


def _find_table_id(token: str, app_token: str, table_name: str) -> Optional[str]:
    for it in _list_tables(token, app_token):
        if str(it.get("name") or "") == table_name:
            return str(it.get("table_id") or "")
    return None


def _list_fields(token: str, app_token: str, table_id: str) -> List[Dict[str, Any]]:
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    data = _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})
    return (data.get("data") or {}).get("items") or []


def _ensure_attachment_field(token: str, app_token: str, table_id: str, field_name: str) -> str:
    fields = _list_fields(token, app_token, table_id)
    for it in fields:
        if str(it.get("field_name") or "") == field_name:
            return str(it.get("field_id") or "")
    body = {"field_name": field_name, "type": 17}
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    _http_json("POST", url, headers={"Authorization": f"Bearer {token}"}, body=body)
    fields = _list_fields(token, app_token, table_id)
    for it in fields:
        if str(it.get("field_name") or "") == field_name:
            return str(it.get("field_id") or "")
    raise RuntimeError("attachment field not found")


def _get_record(token: str, app_token: str, table_id: str, record_id: str) -> Dict[str, Any]:
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
    return _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})


def _update_record(token: str, app_token: str, table_id: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
    body = {"fields": fields}
    return _http_json("PUT", url, headers={"Authorization": f"Bearer {token}"}, body=body)


def _upload_media(token: str, app_token: str, content: bytes, filename: str, ctype: str) -> str:
    parent_type = "bitable_image" if ctype.startswith("image/") else "bitable_file"
    fields = {
        "file_name": filename,
        "parent_type": parent_type,
        "parent_node": app_token,
        "size": str(len(content)),
    }
    files = {"file": (filename, content, ctype)}
    body, ctype_header = _build_multipart(fields, files)
    url = f"{FEISHU_BASE}/open-apis/drive/v1/medias/upload_all"
    status, resp_bytes = _http_request("POST", url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": ctype_header,
    }, data=body, timeout=120)
    resp = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {"status_code": status}
    if resp.get("code") not in (0, "0"):
        raise RuntimeError(f"upload failed: {resp}")
    file_token = (resp.get("data") or {}).get("file_token")
    if not file_token:
        raise RuntimeError(f"upload missing file_token: {resp}")
    return str(file_token)


def _merge_attachments(existing: Any, new_token: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    if isinstance(existing, list):
        for it in existing:
            if isinstance(it, dict) and it.get("file_token"):
                items.append({"file_token": str(it.get("file_token"))})
    items.append({"file_token": new_token})
    return items


def _parse_pairs(args: argparse.Namespace) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    if args.pairs_json:
        data = json.loads(args.pairs_json)
        for it in data:
            if isinstance(it, list) and len(it) == 2:
                pairs.append((str(it[0]), str(it[1])))
            elif isinstance(it, dict) and "record_id" in it and "file_url" in it:
                pairs.append((str(it["record_id"]), str(it["file_url"])))
    if args.pairs_file:
        with open(args.pairs_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for it in data:
            if isinstance(it, list) and len(it) == 2:
                pairs.append((str(it[0]), str(it[1])))
            elif isinstance(it, dict) and "record_id" in it and "file_url" in it:
                pairs.append((str(it["record_id"]), str(it["file_url"])))
    if args.record_id and args.file_url:
        pairs.append((args.record_id, args.file_url))
    return pairs


async def _process_one(task: Task, token: str, app_token: str, table_id: str, field_name: str, mode: str) -> None:
    task.status = "running"
    try:
        content, ctype, fname = _download_file(task.file_url)
        fname = _guess_filename(fname, ctype)
        ctype = ctype.split(";", 1)[0].strip() if ctype else "application/octet-stream"
        file_token = _upload_media(token, app_token, content, fname, ctype)
        task.file_token = file_token

        fields = {}
        if mode == "append":
            rec = _get_record(token, app_token, table_id, task.record_id)
            existing = ((rec.get("data") or {}).get("record") or {}).get("fields") or {}
            fields[field_name] = _merge_attachments(existing.get(field_name), file_token)
        else:
            fields[field_name] = [{"file_token": file_token}]
        _update_record(token, app_token, table_id, task.record_id, fields)
        task.status = "done"
    except Exception as exc:
        task.status = "failed"
        task.error = str(exc)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Async FileUpload standalone")
    parser.add_argument("--app-id")
    parser.add_argument("--app-secret")
    parser.add_argument("--tenant-token")
    parser.add_argument("--app-token", required=True)
    parser.add_argument("--table-id")
    parser.add_argument("--table-name")
    parser.add_argument("--field-name", required=True)
    parser.add_argument("--mode", choices=["append", "overwrite"], default="overwrite")
    parser.add_argument("--record-id")
    parser.add_argument("--file-url")
    parser.add_argument("--pairs-json")
    parser.add_argument("--pairs-file")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--output")
    args = parser.parse_args()

    token = _auth_token(args.app_id, args.app_secret, args.tenant_token)
    app_token = _resolve_app_token(args.app_token, token)
    table_id = args.table_id
    if not table_id and args.table_name:
        table_id = _find_table_id(token, app_token, args.table_name)
    if not table_id:
        raise RuntimeError("table_id or table_name required")

    _ensure_attachment_field(token, app_token, table_id, args.field_name)

    pairs = _parse_pairs(args)
    if not pairs:
        raise RuntimeError("no record/file pairs provided")

    tasks = [Task(record_id=p[0], file_url=p[1]) for p in pairs]
    sem = asyncio.Semaphore(max(1, args.concurrency))

    async def runner(t: Task) -> None:
        async with sem:
            await _process_one(t, token, app_token, table_id, args.field_name, args.mode)

    await asyncio.gather(*[runner(t) for t in tasks])

    summary = {
        "total": len(tasks),
        "done": sum(1 for t in tasks if t.status == "done"),
        "failed": sum(1 for t in tasks if t.status == "failed"),
        "tasks": [t.__dict__ for t in tasks],
    }
    out = _json_dumps(summary)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    print(out)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(_json_dumps({"error": str(exc)}))
        sys.exit(1)
