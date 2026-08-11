#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

FEISHU_BASE = "https://open.feishu.cn"


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


def _auth_token(cfg: Dict[str, Any]) -> str:
    if cfg.get("tenant_access_token"):
        return str(cfg.get("tenant_access_token"))
    _load_dotenv()
    app_id = str(cfg.get("app_id") or os.getenv("FEISHU_APP_ID", ""))
    app_secret = str(cfg.get("app_secret") or os.getenv("FEISHU_APP_SECRET", ""))
    if not app_id or not app_secret:
        raise RuntimeError("app_id/app_secret required")
    return _get_tenant_token(app_id, app_secret)


def _list_tables(token: str, app_token: str) -> List[Dict[str, Any]]:
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables"
    data = _http_json("GET", url, headers={"Authorization": f"Bearer {token}"})
    return (data.get("data") or {}).get("items") or []


def _find_table_id(token: str, app_token: str, name: str) -> Optional[str]:
    for it in _list_tables(token, app_token):
        if str(it.get("name") or "") == name:
            return str(it.get("table_id") or "")
    return None


def _create_table(token: str, app_token: str, name: str, fields: List[Dict[str, Any]], default_view_name: str) -> str:
    body = {"table": {"name": name, "default_view_name": default_view_name, "fields": fields}}
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables"
    data = _http_json("POST", url, headers={"Authorization": f"Bearer {token}"}, body=body)
    if data.get("code") not in (0, "0"):
        raise RuntimeError(f"create table failed: {data}")
    table_id = (data.get("data") or {}).get("table_id") or ((data.get("data") or {}).get("table") or {}).get("table_id")
    if not table_id:
        raise RuntimeError(f"create table missing table_id: {data}")
    return str(table_id)


def _create_records(token: str, app_token: str, table_id: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
    body = {"records": records, "field_key": "name"}
    return _http_json("POST", url, headers={"Authorization": f"Bearer {token}"}, body=body)


def _search_by_key(token: str, app_token: str, table_id: str, field_name: str, value: str) -> Optional[str]:
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
    body = {
        "filter": {
            "conjunction": "and",
            "conditions": [{"field_name": field_name, "operator": "is", "value": [value]}],
        }
    }
    data = _http_json("POST", url, headers={"Authorization": f"Bearer {token}"}, body=body)
    items = (data.get("data") or {}).get("items") or []
    if not items:
        return None
    rec = items[0]
    return rec.get("record_id")


def _update_record(token: str, app_token: str, table_id: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{FEISHU_BASE}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
    body = {"fields": fields}
    return _http_json("PUT", url, headers={"Authorization": f"Bearer {token}"}, body=body)


def _template() -> Dict[str, Any]:
    return {
        "app_id": "cli_xxx",
        "app_secret": "sec_xxx",
        "app_token": "https://your.feishu.cn/base/bascnXXX",
        "table": {
            "name": "Content",
            "default_view_name": "Table View",
            "fields": [
                {"field_name": "Title", "type": 1},
                {"field_name": "Status", "type": 3, "property": {"options": [{"name": "Todo"}, {"name": "Done"}]}},
                {"field_name": "Attachment", "type": 17}
            ]
        },
        "records": [
            {"fields": {"Title": "hello"}}
        ],
        "write_mode": "create",
        "upsert_key": {"field_name": "Title"}
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision table and records")
    parser.add_argument("--config")
    parser.add_argument("--stdin", action="store_true")
    args = parser.parse_args()

    if not args.config and not args.stdin:
        print(_json_dumps(_template()))
        return

    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        raw = sys.stdin.read().strip()
        cfg = json.loads(raw) if raw else {}

    token = _auth_token(cfg)
    app_token = _resolve_app_token(str(cfg.get("app_token")), token)

    table_cfg = cfg.get("table") or {}
    table_name = str(table_cfg.get("name") or "")
    if not table_name:
        raise RuntimeError("table.name required")

    default_view = str(table_cfg.get("default_view_name") or "Table View")
    fields = table_cfg.get("fields") or []

    table_id = _find_table_id(token, app_token, table_name)
    if not table_id:
        table_id = _create_table(token, app_token, table_name, fields, default_view)

    records = cfg.get("records") or []
    if not records:
        print(_json_dumps({"table_id": table_id, "records": 0}))
        return

    mode = str(cfg.get("write_mode") or "create")
    if mode == "upsert":
        key = ((cfg.get("upsert_key") or {}).get("field_name"))
        if not key:
            raise RuntimeError("upsert_key.field_name required for upsert")
        results = []
        for rec in records:
            fields_obj = rec.get("fields") if isinstance(rec, dict) else None
            if not isinstance(fields_obj, dict):
                continue
            if key not in fields_obj:
                raise RuntimeError(f"upsert key missing: {key}")
            rid = _search_by_key(token, app_token, table_id, key, str(fields_obj.get(key)))
            if rid:
                results.append(_update_record(token, app_token, table_id, rid, fields_obj))
            else:
                results.append(_create_records(token, app_token, table_id, [{"fields": fields_obj}]))
        print(_json_dumps({"table_id": table_id, "results": results}))
    else:
        resp = _create_records(token, app_token, table_id, records)
        print(_json_dumps({"table_id": table_id, "response": resp}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(_json_dumps({"error": str(exc)}))
        sys.exit(1)
