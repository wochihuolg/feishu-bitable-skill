# Feishu Bitable Skill

一个面向 Codex 的飞书多维表格与文档发布 Skill。

它把飞书 OpenAPI 封装成可复用的工作流，支持：

- 创建和管理多维表格、字段与记录
- 按业务字段执行新增或更新（upsert）
- 上传附件并写入多维表格附件字段
- 将 Markdown 转换为飞书文档块
- 创建飞书文档或向已有文档追加 Markdown 内容
- 通过飞书 Base、Wiki 或 Docx 链接解析资源 token

## 安装

将整个目录放到 Codex Skill 目录：

```text
~/.codex/skills/feishu-bitable/
```

然后重启 Codex。可以使用 `$feishu-bitable`，也可以直接提出飞书多维表格、飞书文档或 Markdown 发布任务。

## 配置

在 Skill 目录运行：

```bash
python3 scripts/configure.py
python3 scripts/configure.py --check
```

配置脚本会隐藏输入 App Secret，并将凭据保存到本地 `.env`。`.env` 不应提交到 Git、聊天或共享压缩包中。

飞书应用只应申请实际需要的多维表格、文档、云盘和 Wiki 权限，并将目标 Base 或文档添加为应用协作者。

## 常用命令

```bash
# 查看或创建多维表格
python3 scripts/feishu_cli.py list-tables --app-token <BASE_TOKEN_OR_URL>
python3 scripts/feishu_cli.py create-table --app-token <BASE_TOKEN_OR_URL> --name Content

# 写入单条记录
python3 scripts/feishu_cli.py create-record \
  --app-token <BASE_TOKEN_OR_URL> \
  --table-id <TABLE_ID> \
  --fields-file record.json

# 将 Markdown 转换为飞书块，不发起网络请求
python3 scripts/markdown_to_feishu.py convert --input article.md

# 发布为新的飞书文档
python3 scripts/markdown_to_feishu.py publish --input article.md --title "Article title"
```

批量建表和记录可使用 `scripts/provision_table_and_records.py`；批量附件可使用 `scripts/async_fileupload.py`。

## 安全边界

- 不要在命令行参数、日志、Markdown 或 Git 中写入 App Secret、访问令牌或 PAT。
- 执行批量写入、更新或删除前，应先确认目标 Base、表格和记录范围。
- 附件上传会将远程文件下载到内存后再上传，只使用可信 URL，并注意文件大小。
- Markdown 中的图片目前会作为链接文字写入文档，不会自动上传图片二进制。

## 目录结构

```text
SKILL.md                 Codex Skill 入口与工作流说明
agents/openai.yaml       Skill 展示信息
references/              权限、字段、API 和发布参考
scripts/                 配置、Base、附件和 Markdown 工具
```

## License

MIT
