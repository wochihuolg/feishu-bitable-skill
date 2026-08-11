#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional


FEISHU_BASE = "https://open.feishu.cn"
SKILL_DIR = Path(__file__).resolve().parent.parent


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def load_dotenv() -> None:
    path = SKILL_DIR / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def http_json(method: str, path: str, *, token: Optional[str] = None, body: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{FEISHU_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
            code = detail.get("code", exc.code)
            message = detail.get("msg") or detail.get("message") or "request failed"
            raise RuntimeError(f"Feishu API error {code}: {message}") from exc
        except json.JSONDecodeError:
            raise RuntimeError(f"Feishu API HTTP {exc.code}") from exc
    if result.get("code") not in (0, "0", None):
        raise RuntimeError(f"Feishu API error {result.get('code')}: {result.get('msg', 'request failed')}")
    return result


def tenant_token() -> str:
    load_dotenv()
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise RuntimeError("Credentials missing. Run: python3 scripts/configure.py")
    result = http_json(
        "POST",
        "/open-apis/auth/v3/tenant_access_token/internal",
        body={"app_id": app_id, "app_secret": app_secret},
    )
    token = result.get("tenant_access_token")
    if not token:
        raise RuntimeError("Feishu response did not contain tenant_access_token")
    return str(token)


INLINE_RE = re.compile(
    r"(\[([^\]]+)\]\((https?://[^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|~~([^~]+)~~|(?<!\*)\*([^*]+)\*(?!\*))"
)


def inline_elements(text: str) -> list[dict[str, Any]]:
    elements: list[dict[str, Any]] = []
    position = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > position:
            elements.append({"text_run": {"content": text[position:match.start()]}})
        if match.group(2) is not None:
            elements.append({"text_run": {"content": match.group(2), "text_element_style": {"link": {"url": match.group(3)}}}})
        elif match.group(4) is not None:
            elements.append({"text_run": {"content": match.group(4), "text_element_style": {"inline_code": True}}})
        elif match.group(5) is not None:
            elements.append({"text_run": {"content": match.group(5), "text_element_style": {"bold": True}}})
        elif match.group(6) is not None:
            elements.append({"text_run": {"content": match.group(6), "text_element_style": {"strikethrough": True}}})
        elif match.group(7) is not None:
            elements.append({"text_run": {"content": match.group(7), "text_element_style": {"italic": True}}})
        position = match.end()
    if position < len(text):
        elements.append({"text_run": {"content": text[position:]}})
    return elements or [{"text_run": {"content": ""}}]


def text_block(kind: str, block_type: int, content: str, style: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"elements": inline_elements(content)}
    if style:
        payload["style"] = style
    return {"block_type": block_type, kind: payload}


def strip_frontmatter(lines: list[str]) -> tuple[list[str], Optional[str]]:
    if not lines or lines[0].strip() != "---":
        return lines, None
    for index in range(1, min(len(lines), 100)):
        if lines[index].strip() == "---":
            title = None
            for item in lines[1:index]:
                match = re.match(r"^title:\s*[\"']?(.*?)[\"']?\s*$", item, re.IGNORECASE)
                if match:
                    title = match.group(1)
                    break
            return lines[index + 1 :], title
    return lines, None


def markdown_to_blocks(markdown: str) -> tuple[list[dict[str, Any]], Optional[str]]:
    lines, frontmatter_title = strip_frontmatter(markdown.replace("\r\n", "\n").split("\n"))
    blocks: list[dict[str, Any]] = []
    paragraph: list[str] = []
    code_lines: list[str] = []
    code_language = ""
    in_code = False
    first_heading: Optional[str] = None

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(text_block("text", 2, "\n".join(paragraph).strip()))
            paragraph.clear()

    for line in lines + [""]:
        fence = re.match(r"^```\s*([^`]*)$", line)
        if fence:
            if in_code:
                content = "\n".join(code_lines)
                blocks.append(text_block("code", 14, content, {"language": 1}))
                code_lines.clear()
                in_code = False
            else:
                flush_paragraph()
                in_code = True
                code_language = fence.group(1).strip()
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            continue
        heading = re.match(r"^(#{1,9})\s+(.+?)\s*#*\s*$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            content = heading.group(2)
            if first_heading is None:
                first_heading = re.sub(r"[*_~`]", "", content)
            blocks.append(text_block(f"heading{level}", level + 2, content))
            continue
        if re.match(r"^\s*(---+|\*\*\*+)\s*$", line):
            flush_paragraph()
            blocks.append({"block_type": 22, "divider": {}})
            continue
        task = re.match(r"^\s*[-*+]\s+\[([ xX])\]\s+(.+)$", line)
        if task:
            flush_paragraph()
            block = text_block("todo", 17, task.group(2))
            block["todo"]["style"] = {"done": task.group(1).lower() == "x"}
            blocks.append(block)
            continue
        bullet = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if bullet:
            flush_paragraph()
            blocks.append(text_block("bullet", 12, bullet.group(1)))
            continue
        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if ordered:
            flush_paragraph()
            blocks.append(text_block("ordered", 13, ordered.group(1)))
            continue
        quote = re.match(r"^\s*>\s?(.*)$", line)
        if quote:
            flush_paragraph()
            blocks.append(text_block("quote", 15, quote.group(1)))
            continue
        image = re.fullmatch(r"\s*!\[([^\]]*)\]\(([^)]+)\)\s*", line)
        if image:
            flush_paragraph()
            label = image.group(1) or "Image"
            blocks.append(text_block("text", 2, f"{label}: {image.group(2)}"))
            continue
        paragraph.append(line)

    if in_code:
        blocks.append(text_block("code", 14, "\n".join(code_lines), {"language": 1}))
    _ = code_language
    return blocks, frontmatter_title or first_heading


def create_document(token: str, title: str) -> str:
    result = http_json("POST", "/open-apis/docx/v1/documents", token=token, body={"title": title})
    document = (result.get("data") or {}).get("document") or {}
    document_id = document.get("document_id")
    if not document_id:
        raise RuntimeError("Create document response did not contain document_id")
    return str(document_id)


def append_blocks(token: str, document_id: str, blocks: list[dict[str, Any]]) -> None:
    encoded_id = urllib.parse.quote(document_id, safe="")
    path = f"/open-apis/docx/v1/documents/{encoded_id}/blocks/{encoded_id}/children?document_revision_id=-1"
    for start in range(0, len(blocks), 50):
        http_json("POST", path, token=token, body={"children": blocks[start : start + 50], "index": -1})


def read_markdown(args: argparse.Namespace) -> str:
    if args.input:
        return Path(args.input).read_text(encoding="utf-8")
    if args.text is not None:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise RuntimeError("Provide --input, --text, or Markdown on stdin")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Markdown to Feishu blocks or publish to Docx")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("convert", "publish"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--input", help="UTF-8 Markdown file")
        sub.add_argument("--text", help="Markdown text")
        sub.add_argument("--output", help="write result JSON to a file")
        if command == "publish":
            sub.add_argument("--title", help="new document title; defaults to frontmatter or first heading")
            sub.add_argument("--document-id", help="append to an existing document instead of creating one")

    args = parser.parse_args()
    markdown = read_markdown(args)
    blocks, detected_title = markdown_to_blocks(markdown)

    if args.command == "convert":
        result: dict[str, Any] = {"blocks": blocks, "count": len(blocks), "detected_title": detected_title}
    else:
        token = tenant_token()
        document_id = args.document_id or create_document(token, args.title or detected_title or "Untitled")
        append_blocks(token, document_id, blocks)
        result = {
            "document_id": document_id,
            "url": f"https://feishu.cn/docx/{document_id}",
            "blocks_written": len(blocks),
            "created": not bool(args.document_id),
        }

    rendered = json_dumps(result)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json_dumps({"error": str(exc)}))
        raise SystemExit(1)
