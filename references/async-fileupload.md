# Async FileUpload Design (standalone)

Goal
- Provide async, retryable attachment uploads for Bitable records.

Suggested inputs
- app_id + app_secret OR tenant_access_token
- app_token (token or base/wiki link)
- table_id or table_name
- field_id or field_name
- record_ids: ["rec...", ...]
- file_urls: ["http(s)://...", ...]
- mode: append | overwrite
- optional: file_names, mime_types

Worker steps
1) Download file_url to temp file.
2) Upload via Drive media: `/open-apis/drive/v1/medias/upload_all`
   - parent_type: bitable_file or bitable_image
   - parent_node: app_token
3) Update the record attachment field with file_token.
   - append: merge with existing attachment list
   - overwrite: replace attachment list
4) Record task status and errors; retry on transient failures.

Status reporting
- Track batch/task state: queued, running, done, failed.
- Return counts: total, done, failed, running, queued.

Notes
- record_ids and file_urls must align; a single record_id can pair with multiple file_urls.
- Ensure the app has Drive + Bitable permissions; otherwise uploads may fail.
