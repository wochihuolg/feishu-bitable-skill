# Bitable Field Types and Record Write Shapes

Use these shapes for "fields" payloads (field_key=name by default).

- 1 text
  - "Title": "plain text"

- 2 number
  - "Amount": 12.34

- 3 single select
  - "Status": "In Progress"

- 4 multi select
  - "Tags": ["A", "B"]

- 5 date (ms timestamp)
  - "DueDate": 1719830400000

- 7 checkbox
  - "Done": true

- 11 user
  - "Owner": [{"id": "ou_xxx"}]

- 13 phone
  - "Phone": "+8613800138000"

- 15 url
  - "Link": {"text": "Open", "link": "https://open.feishu.cn"}

- 17 attachment
  - "Attachment": [{"file_token": "boxcn..."}]

- 18/21 link record
  - "Rel": {"link_record_ids": ["recxxx"]}

- 22 location
  - "Location": {"location": "116.352681,40.01437", "address": "Road 1"}

System fields (1001..1005) are read-only on write.

Notes
- For select fields, option names can be created on demand or pre-seeded.
- For attachments, upload first to get file_token, then update the record.
