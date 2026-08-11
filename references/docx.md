# Docx and Markdown Publishing

Core endpoints
- POST /open-apis/docx/v1/documents (create)
- GET  /open-apis/docx/v1/documents/{document_id}
- GET  /open-apis/docx/v1/documents/{document_id}/blocks
- POST /open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children (write blocks)

Standard workflows

1. Convert Markdown without writing to Feishu:
   `python3 scripts/markdown_to_feishu.py convert --input article.md`
2. Create and publish a new document:
   `python3 scripts/markdown_to_feishu.py publish --input article.md --title "Title"`
3. Append to an existing document:
   `python3 scripts/markdown_to_feishu.py publish --input update.md --document-id DOCX_TOKEN`
4. Read document blocks:
   `python3 scripts/feishu_cli.py list-docx-blocks --document-id DOCX_TOKEN`

Markdown mapping

- Paragraph, H1-H9, unordered and ordered lists, task items, quote, fenced code, and divider map to native Feishu blocks.
- Bold, italic, strikethrough, inline code, and HTTP(S) links map to text element styles.
- YAML frontmatter `title` or the first heading supplies the default document title.
- Markdown image syntax becomes linked fallback text. The publisher does not upload image binaries into Docx.
- Deeply nested lists and language-specific code highlighting are flattened to stable Docx blocks.

Token resolution
- docx token is the path segment after /docx/ in the URL.
- wiki links require wiki node resolution before you get obj_token.
- Use wiki get_node to map wiki token -> obj_type + obj_token.

Permissions
- Missing docx scope returns 403; ensure the app has docx permissions.
- tenant_access_token only works if the app is added as a collaborator.
- After changing app permissions, publish a new app version before retrying.
