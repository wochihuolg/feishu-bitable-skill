---
name: feishu-bitable
description: End-to-end Feishu OpenAPI workflows for Bitable tables and records, Docx documents, Markdown-to-Feishu publishing, and async attachment uploads. Use when tasks mention Feishu, Bitable, wiki/base/docx links, app_token/table_id/record_id, Markdown publishing, document writing, attachments, Drive media upload, or Docx APIs, including setups where only app_id and app_secret are available.
---

# Feishu Bitable + Docx Publishing

## Quick Start

1) Check credentials before making API calls.
   - If `.env` is absent or incomplete, tell the user to run `python3 scripts/configure.py` in this skill directory.
   - Never ask the user to paste `App Secret` into chat when the local hidden prompt is available.
   - Fetch `tenant_access_token` via `/open-apis/auth/v3/tenant_access_token/internal`.
   - Never log secrets or access tokens.

2) Resolve app_token from base/wiki URL.
   - If wiki link, call wiki get_node to map to obj_token (bitable).

3) Load only the references needed for the request.
   - Installation, credentials, and permissions: `references/setup.md`.
   - API map: `references/api-map.md`.
   - Field type write formats: `references/field-types.md`.
   - Async FileUpload design: `references/async-fileupload.md`.
   - Docx and Markdown publishing: `references/docx.md`.
   - Interface templates: `references/interface-templates.md`.

## Workflow Decision Tree

- Need Bitable CRUD? Use Bitable table/field/record endpoints.
- Need attachments? Upload to Drive/Bitable, then update attachment fields.
- Need async attachments? Use the async queue/worker pattern in `references/async-fileupload.md`.
- Need to publish or write Markdown? Run `scripts/markdown_to_feishu.py publish`.
- Need only Feishu block JSON? Run `scripts/markdown_to_feishu.py convert`.
- Need other Docx operations? Use Docx OpenAPI endpoints and verify permissions first.

## Bitable Core Workflow

1) Resolve app_token.
   - From base/wiki link or token.
   - Use wiki resolution when only wiki link is provided.

2) Resolve table and field.
   - Prefer `table_id` and `field_id` when known.
   - Otherwise list tables/fields and map by name.

3) Write records.
   - Use `field_key` or `field_key_type` consistently.
   - For upsert behavior, search by a stable business key and update/add.

4) Attachments.
   - Upload media to Bitable or Drive, then write the attachment field with file_token.
   - For large or batch uploads, use async FileUpload.

## Async FileUpload Workflow

- Implement or call a queue/worker that does:
  download file_url -> upload via drive medias/upload_all -> update record attachment field.
- Track batch/task status (queued/running/done/failed) and return summary.
- Keep record_ids and file_urls aligned (or a single record_id for many files).

## Docx Workflow

- For Markdown input, preserve headings, paragraphs, lists, tasks, quotes, code blocks, dividers, links, and basic inline emphasis.
- Create a Docx document or append to an existing `document_id`, then add converted blocks in batches.
- Return the `document_id` and document URL after publishing.
- Use wiki node resolution if a docx is under a wiki link.
- Keep app permissions in mind; missing docx scope will return 403.
- Treat Markdown images as linked fallback text. Do not claim that image binaries were uploaded unless an upload call succeeded.

## Safety and Logging

- Never print app_secret or tenant_access_token.
- Avoid hardcoding tokens in files.
- Store `.env` with file mode `0600` and never include it in a shared archive.
- Respect rate limits and avoid parallel writes to the same table.
- Before destructive or bulk writes, summarize the target document/table and ask for confirmation when the user has not already explicitly requested execution.

## Interface Templates

Use `references/interface-templates.md` for HTTP request/response shapes that are safe to reuse in a standalone wrapper service.

## Scripts

- `scripts/feishu_cli.py`: CLI for Bitable and Docx operations.
- `scripts/async_fileupload.py`: local async attachment uploader (no server).
- `scripts/provision_table_and_records.py`: create table + write records from JSON config or stdin.
- `scripts/markdown_to_feishu.py`: convert Markdown to Feishu blocks or publish it to a new/existing Docx document.
- `scripts/configure.py`: securely prompt for App ID and App Secret, save local credentials, and optionally verify them.
