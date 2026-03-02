---
description: "Integrate ZeroGate-Red-Teaming with Claude Code as an MCP server for natural language codebase analysis."
---

# MCP Server (Claude Code Integration)

ZeroGate-Red-Teaming can run as an MCP (Model Context Protocol) server, enabling seamless integration with Claude Code and other MCP clients.

## Quick Setup

**If installed via pip** (and `ZeroGate-Red-Teaming` is on your PATH):

```bash
claude mcp add --transport stdio ZeroGate-Red-Teaming \
  --env TARGET_REPO_PATH=/absolute/path/to/your/project \
  --env CYPHER_PROVIDER=openai \
  --env CYPHER_MODEL=gpt-4 \
  --env CYPHER_API_KEY=your-api-key \
  -- ZeroGate-Red-Teaming mcp-server
```

**If installed from source:**

```bash
claude mcp add --transport stdio ZeroGate-Red-Teaming \
  --env TARGET_REPO_PATH=/absolute/path/to/your/project \
  --env CYPHER_PROVIDER=openai \
  --env CYPHER_MODEL=gpt-4 \
  --env CYPHER_API_KEY=your-api-key \
  -- uv run --directory /path/to/ZeroGate-Red-Teaming ZeroGate-Red-Teaming mcp-server
```

### Using Current Directory

```bash
cd /path/to/your/project

claude mcp add --transport stdio ZeroGate-Red-Teaming \
  --env TARGET_REPO_PATH="$(pwd)" \
  --env CYPHER_PROVIDER=google \
  --env CYPHER_MODEL=gemini-2.0-flash \
  --env CYPHER_API_KEY=your-google-api-key \
  -- uv run --directory /absolute/path/to/ZeroGate-Red-Teaming ZeroGate-Red-Teaming mcp-server
```

## Prerequisites

```bash
git clone https://github.com/krrishitejas/ZeroGate-Red-Teaming.git
cd ZeroGate-Red-Teaming
uv sync

docker run -p 7687:7687 -p 7444:7444 memgraph/memgraph-platform
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_projects` | List all indexed projects in the knowledge graph database |
| `delete_project` | Delete a specific project from the knowledge graph database |
| `wipe_database` | Completely wipe the entire database (cannot be undone) |
| `index_repository` | Parse and ingest the repository into the knowledge graph |
| `query_code_graph` | Query the codebase knowledge graph using natural language |
| `get_code_snippet` | Retrieve source code for a function, class, or method by qualified name |
| `surgical_replace_code` | Surgically replace an exact code block using diff-match-patch |
| `read_file` | Read file contents with pagination support |
| `write_file` | Write content to a file |
| `list_directory` | List directory contents |

## Example Usage

```
> Index this repository
> What functions call UserService.create_user?
> Update the login function to add rate limiting
```

## LLM Provider Options

=== "OpenAI"

    ```bash
    --env CYPHER_PROVIDER=openai \
    --env CYPHER_MODEL=gpt-4 \
    --env CYPHER_API_KEY=sk-...
    ```

=== "Google Gemini"

    ```bash
    --env CYPHER_PROVIDER=google \
    --env CYPHER_MODEL=gemini-2.5-flash \
    --env CYPHER_API_KEY=...
    ```

=== "Ollama (free, local)"

    ```bash
    --env CYPHER_PROVIDER=ollama \
    --env CYPHER_MODEL=llama3.2
    ```

## Multi-Repository Setup

Add separate named instances for different projects:

```bash
claude mcp add --transport stdio ZeroGate-Red-Teaming-backend \
  --env TARGET_REPO_PATH=/path/to/backend \
  --env CYPHER_PROVIDER=openai \
  --env CYPHER_MODEL=gpt-4 \
  --env CYPHER_API_KEY=your-api-key \
  -- uv run --directory /path/to/ZeroGate-Red-Teaming ZeroGate-Red-Teaming mcp-server

claude mcp add --transport stdio ZeroGate-Red-Teaming-frontend \
  --env TARGET_REPO_PATH=/path/to/frontend \
  --env CYPHER_PROVIDER=openai \
  --env CYPHER_MODEL=gpt-4 \
  --env CYPHER_API_KEY=your-api-key \
  -- uv run --directory /path/to/ZeroGate-Red-Teaming ZeroGate-Red-Teaming mcp-server
```

!!! warning
    Only one repository can be indexed at a time per MCP instance. When you index a new repository, the previous repository's data is automatically cleared.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Can't find uv/ZeroGate-Red-Teaming | Use absolute paths from `which uv` |
| Wrong repository analyzed | Set `TARGET_REPO_PATH` to an absolute path |
| Memgraph connection failed | Ensure `docker ps` shows Memgraph running |
| Tools not showing | Run `claude mcp list` to verify installation |

## Remove

```bash
claude mcp remove ZeroGate-Red-Teaming
```
