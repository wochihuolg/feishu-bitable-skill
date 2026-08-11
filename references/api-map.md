# API Map (Feishu OpenAPI)

## Feishu OpenAPI (core)

- Auth
  - POST /open-apis/auth/v3/tenant_access_token/internal

- Wiki token resolution
  - GET /open-apis/wiki/v2/spaces/get_node?token={wiki_token}
  - GET /open-apis/wiki/v2/spaces/nodes/{wiki_token}

- Bitable tables
  - GET  /open-apis/bitable/v1/apps/{app_token}/tables
  - POST /open-apis/bitable/v1/apps/{app_token}/tables
  - PATCH/DELETE /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}

- Bitable fields
  - GET  /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields
  - POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields
  - PUT  /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}

- Bitable records
  - POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records
  - POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search
  - PUT  /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}
  - POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete

- Drive media (attachments)
  - POST /open-apis/drive/v1/medias/upload_all
  - GET  /open-apis/drive/v1/medias/{file_token}/download
  - GET  /open-apis/drive/v1/medias/batch_get_tmp_download_url

- Docx
  - POST /open-apis/docx/v1/documents
  - GET  /open-apis/docx/v1/documents/{document_id}
  - GET  /open-apis/docx/v1/documents/{document_id}/blocks
  - POST /open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children

## Wrapper (optional)

If you build a wrapper service, keep inputs consistent with Feishu OpenAPI:
- app_id/app_secret or tenant_access_token
- app_token accepts token or base/wiki link
- table_id or table_name accepted
- field_id or field_name accepted for attachments
