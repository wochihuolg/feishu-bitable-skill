# Interface Templates (standalone)

Use these as reusable HTTP shapes for a standalone wrapper service.
All examples use placeholders and must be filled at runtime.

## Auth: tenant_access_token

Request
- POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
- Headers: Content-Type: application/json; charset=utf-8
- Body:
```
{
  "app_id": "cli_xxx",
  "app_secret": "sec_xxx"
}
```

Response (success)
```
{
  "code": 0,
  "tenant_access_token": "t-xxx",
  "expire": 7200
}
```

## Bitable: create app

Request
- POST https://open.feishu.cn/open-apis/bitable/v1/apps
- Headers: Authorization: Bearer {tenant_access_token}
- Body:
```
{
  "name": "My Bitable"
}
```

## Bitable: list tables

Request
- GET https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables
- Headers: Authorization: Bearer {tenant_access_token}

## Bitable: create table with fields

Request
- POST https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables
- Headers: Authorization: Bearer {tenant_access_token}
- Body:
```
{
  "table": {
    "name": "Content",
    "default_view_name": "Table View",
    "fields": [
      {"field_name": "Title", "type": 1},
      {"field_name": "Status", "type": 3, "property": {"options": [{"name": "Todo"}, {"name": "Done"}]}},
      {"field_name": "Attachment", "type": 17}
    ]
  }
}
```

## Bitable: create record

Request
- POST https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records
- Headers: Authorization: Bearer {tenant_access_token}
- Body:
```
{
  "fields": {"Title": "Hello"},
  "field_key": "name"
}
```

## Bitable: search records

Request
- POST https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search
- Headers: Authorization: Bearer {tenant_access_token}
- Body:
```
{
  "filter": {
    "conjunction": "and",
    "conditions": [{"field_name": "Title", "operator": "is", "value": ["Hello"]}]
  }
}
```

## Attachments: upload media to Bitable

Request
- POST https://open.feishu.cn/open-apis/drive/v1/medias/upload_all
- Headers: Authorization: Bearer {tenant_access_token}
- Form fields:
  - file_name: "demo.pdf"
  - parent_type: bitable_file
  - parent_node: {app_token}
  - size: {bytes}
  - file: (binary)

Response (success)
```
{
  "code": 0,
  "data": {"file_token": "boxcn..."}
}
```

## Attachments: update record with file_token

Request
- PUT https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}
- Headers: Authorization: Bearer {tenant_access_token}
- Body:
```
{
  "fields": {"Attachment": [{"file_token": "boxcn..."}]}
}
```

## Docx: create document

Request
- POST https://open.feishu.cn/open-apis/docx/v1/documents
- Headers: Authorization: Bearer {tenant_access_token}
- Body:
```
{
  "title": "My Doc"
}
```

## Docx: list blocks

Request
- GET https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks
- Headers: Authorization: Bearer {tenant_access_token}
