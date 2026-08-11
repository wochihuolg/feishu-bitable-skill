# Installation and Credential Setup

## Install

Extract the archive so the final path is:

```text
~/.codex/skills/feishu-bitable/SKILL.md
```

Restart Codex after installation. Invoke the skill with `$feishu-bitable` or ask for a Feishu, Bitable, Docx, or Markdown publishing task.

## Configure credentials

Create a self-built app in Feishu Open Platform and copy its App ID and App Secret. In a terminal, run:

```bash
cd ~/.codex/skills/feishu-bitable
python3 scripts/configure.py
```

The script uses a hidden prompt for App Secret and writes `.env` with mode `0600`. Do not paste the secret into chat, commit it, or add it to a shared archive.

Verify credentials without printing the token:

```bash
python3 scripts/configure.py --check
```

## Enable Feishu access

Enable only the permissions needed by the intended workflows:

- Bitable app, table, field, and record read/write permissions.
- Docx document and block read/write permissions.
- Drive media upload permissions for attachments.
- Wiki node read permission when resolving wiki links.

Publish the app version after changing permissions. Add the app as a collaborator when the target document, wiki, or Bitable is not app-owned. A `403` usually means permission or collaborator access is missing, not that the credentials are malformed.

## Smoke test

Create local Feishu block JSON without making a network request:

```bash
python3 scripts/markdown_to_feishu.py convert --text '# Hello'
```

Publish a Markdown file to a new Feishu document:

```bash
python3 scripts/markdown_to_feishu.py publish --input article.md --title 'Article title'
```

Append Markdown to an existing document:

```bash
python3 scripts/markdown_to_feishu.py publish --input update.md --document-id DOCX_TOKEN
```
