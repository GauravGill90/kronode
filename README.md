<p align="center">
  <img src="assets/banner.svg" alt="Kronode" width="600" />
</p>

<p align="center">
  <strong>Extract team conventions from git history. Serve them to any AI coding tool via MCP.</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> · <a href="#setup-your-ai-tool">Setup AI Tool</a> · <a href="#modes">Modes</a> · <a href="#mcp-tools">MCP Tools</a>
</p>

Three commands. Zero API keys. Works with Claude Code, Cursor, Codex, Copilot, and 10+ more.

```bash
pip install kronode
kronode init .
kronode ingest
kronode serve
```

---

## What it does

Kronode reads your local git repository and extracts:

- **Conventions** — commit message patterns, team naming rules, directory structure
- **Documentation** — README, docs/, architecture decisions from markdown files
- **PR review knowledge** — what reviewers actually teach in code reviews (optional)

Then serves it all via [MCP](https://modelcontextprotocol.io/) to any AI coding tool — so your AI assistant knows your team's patterns, not just generic best practices.

## Quick Start

```bash
# Install
pip install kronode

# Point to your repo
cd ~/projects/your-repo
kronode init .

# Extract conventions + docs from git history
kronode ingest

# Optional: also fetch PR review comments (uses gh CLI auth)
kronode ingest --with-prs

# Start MCP server
kronode serve
```

Then connect your AI tool (see [Setup](#setup-your-ai-tool) below).

## How it works

```
Your Git Repo               Kronode                    AI Coding Tool
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ git log      │────▸│ Convention       │     │ Claude Code      │
│ git blame    │     │ Extraction       │     │ Cursor           │
│ docs/*.md    │────▸│                  │◂───▸│ Codex            │
│ PR reviews   │────▸│ SQLite DB        │ MCP │ Copilot          │
│ (optional)   │     │ Local Embeddings │     │ Windsurf         │
└──────────────┘     └──────────────────┘     │ + 7 more         │
                                               └──────────────────┘
```

Everything runs locally. No data leaves your machine unless you opt into BYOK mode.

## CLI Reference

| Command | Description |
|---------|-------------|
| `kronode init .` | Initialize for a local repo |
| `kronode ingest` | Extract conventions + docs from git history |
| `kronode ingest --with-prs` | Also fetch PR review comments (uses `gh` CLI or `--token`) |
| `kronode serve` | Start MCP server (stdio) |
| `kronode serve --http` | Start MCP server (HTTP/SSE for Cursor, remote) |
| `kronode query "task" -f file.py` | Test context retrieval from terminal |
| `kronode setup <tool>` | Print MCP config for an AI tool |
| `kronode status` | Show convention/doc counts |
| `kronode add "convention rule"` | Manually add a convention |
| `kronode purge` | Delete all ingested data |

## Setup Your AI Tool

### Claude Code
```bash
claude mcp add kronode -- kronode serve
```

### Cursor
Add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "kronode": {
      "command": "kronode",
      "args": ["serve"]
    }
  }
}
```

### OpenAI Codex
Add to `~/.codex/config.toml`:
```toml
[mcp_servers.kronode]
command = "kronode"
args = ["serve"]

[mcp_servers.kronode.tools.get_context]
approval_mode = "approve"

[mcp_servers.kronode.tools.get_doc]
approval_mode = "approve"
```

### GitHub Copilot (VS Code)
Add to `.vscode/mcp.json`:
```json
{
  "servers": {
    "kronode": {
      "command": "kronode",
      "args": ["serve"]
    }
  }
}
```

Run `kronode setup --list` to see all supported tools.

## Modes

### Local Mode (default)
Zero API keys, zero network. Reads from your `.git/` directory.

- Conventions from commit message patterns + git structure
- Documentation from markdown files
- Local embeddings via [fastembed](https://github.com/qdrant/fastembed) (ONNX, ~50MB)

### Local + PRs
Add `--with-prs` to also fetch PR review comments. If [gh CLI](https://cli.github.com/) is installed and authenticated, no token needed. Otherwise pass `--token <PAT>`.

```bash
# With gh CLI (recommended)
gh auth login
kronode ingest --with-prs

# Or with explicit PAT
kronode ingest --with-prs --token ghp_xxx
```

### BYOK Mode
Set `OPENAI_API_KEY` for richer LLM-based convention extraction from PR diffs.

```bash
OPENAI_API_KEY=sk-xxx kronode ingest --with-prs
```

## Configuration

Copy `.env.example` to `~/.kronode/.env`:

```bash
# Number of PRs to analyze (default: 200)
KRONODE_PR_COUNT=200

# Minimum confidence threshold (default: 0.5)
KRONODE_MIN_CONFIDENCE=0.5

# Max conventions per query (default: 20)
KRONODE_MAX_CONVENTIONS=20
```

## MCP Tools

Kronode exposes 2 MCP tools:

### `get_context`
Returns everything an AI needs before coding:
- Top conventions ranked by file-level relevance (with match reasons)
- Related documentation from repo markdown
- Action plan summary
- Directly and loosely related issues (if indexed)

### `get_doc`
Returns the full content of a documentation page when `get_context` returned a truncated snippet.

## Tech Stack

- **Python 3.11+** — async throughout
- **SQLite** — zero-config local database (PostgreSQL optional)
- **fastembed** — ONNX local embeddings (~50MB, not 2GB PyTorch)
- **MCP** — Model Context Protocol for AI tool integration
- **click + rich** — CLI framework

## Development

```bash
git clone https://github.com/GauravGill90/kronode.git
cd kronode
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[byok]"
kronode --help
```

## License

MIT
