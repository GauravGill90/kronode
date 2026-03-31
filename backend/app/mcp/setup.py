"""Kronode MCP setup CLI — generates config snippets for every AI coding agent.

Usage:
    python -m app.mcp.setup claude-code --token kron_xxx
    python -m app.mcp.setup cursor --token kron_xxx
    python -m app.mcp.setup copilot --token kron_xxx --remote --url https://api.kronode.dev
    python -m app.mcp.setup --all --token kron_xxx
"""
import argparse
import json
import sys


def _stdio_config(token: str) -> dict:
    """Base stdio config (python -m app.mcp.main --token ...)."""
    return {
        "command": "python",
        "args": ["-m", "app.mcp.main", "--token", token],
        "env": {},
    }


def _http_config(url: str, token: str) -> dict:
    """Base HTTP config for remote MCP."""
    return {
        "url": f"{url}/mcp/sse",
        "headers": {"Authorization": f"Bearer {token}"},
    }


AGENTS = {
    "claude-code": {
        "name": "Claude Code",
        "file": ".mcp.json (project root) or claude mcp add",
        "root_key": "mcpServers",
        "transports": ["stdio", "http"],
        "notes": "Scopes: --scope local (default), --scope project, --scope user",
    },
    "cursor": {
        "name": "Cursor",
        "file": ".cursor/mcp.json",
        "root_key": "mcpServers",
        "transports": ["stdio", "sse", "http"],
        "notes": "Only works in Agent/Composer mode, not Tab autocomplete",
    },
    "windsurf": {
        "name": "Windsurf",
        "file": "~/.codeium/windsurf/mcp_config.json",
        "root_key": "mcpServers",
        "transports": ["stdio", "http"],
        "notes": "100-tool limit. Supports ${env:VAR} syntax",
    },
    "copilot": {
        "name": "GitHub Copilot (VS Code)",
        "file": ".vscode/mcp.json",
        "root_key": "servers",  # NOTE: different from others!
        "transports": ["stdio", "http"],
        "notes": "Root key is 'servers' NOT 'mcpServers'. Agent mode only.",
    },
    "cline": {
        "name": "Cline",
        "file": "cline_mcp_settings.json (via extension UI)",
        "root_key": "mcpServers",
        "transports": ["stdio", "sse"],
        "notes": "No streamable HTTP yet. Configure via MCP Servers icon in nav.",
    },
    "continue": {
        "name": "Continue",
        "file": ".continue/mcpServers/kronode.json",
        "root_key": "mcpServers",
        "transports": ["stdio", "sse", "http"],
        "notes": "Also supports YAML config",
    },
    "amazon-q": {
        "name": "Amazon Q Developer",
        "file": "~/.aws/amazonq/mcp.json or .amazonq/mcp.json",
        "root_key": "mcpServers",
        "transports": ["stdio", "http"],
        "notes": "Admin whitelisting via IAM Identity Center",
    },
    "jetbrains": {
        "name": "JetBrains AI Assistant",
        "file": "mcp.json or Settings > Tools > AI Assistant > MCP",
        "root_key": "mcpServers",
        "transports": ["http", "sse", "stdio"],
        "notes": "Junie only supports stdio",
    },
    "zed": {
        "name": "Zed",
        "file": "settings.json (Zed settings)",
        "root_key": "context_servers",  # NOTE: different!
        "transports": ["stdio"],
        "notes": "Root key is 'context_servers'. No native HTTP — use mcp-remote wrapper.",
    },
    "tabnine": {
        "name": "Tabnine",
        "file": ".tabnine/mcp_servers.json or ~/.tabnine/mcp_servers.json",
        "root_key": "mcpServers",
        "transports": ["stdio", "sse", "http"],
        "notes": "Admin allow-lists available",
    },
    "cody": {
        "name": "Sourcegraph Cody",
        "file": ".vscode/mcp.json or VS Code settings",
        "root_key": "servers",
        "transports": ["stdio", "http"],
        "notes": "Supports OAuth Dynamic Client Registration",
    },
    "codex": {
        "name": "OpenAI Codex",
        "file": "~/.codex/config.toml or .codex/config.toml",
        "root_key": "mcpServers",
        "transports": ["stdio", "http"],
        "notes": "Use 'codex mcp add' CLI command. Supports TOML config.",
    },
}


def generate_config(agent: str, token: str, remote: bool, url: str) -> str:
    """Generate config snippet for a specific agent."""
    info = AGENTS[agent]
    root_key = info["root_key"]

    if remote:
        server_config = _http_config(url, token)
    else:
        server_config = _stdio_config(token)

    # Special case: claude-code CLI command
    if agent == "claude-code" and not remote:
        lines = [
            f"# {info['name']} — {info['file']}",
            f"# {info['notes']}",
            "",
            "# Option 1: CLI command",
            f"claude mcp add kronode -- python -m app.mcp.main --token {token}",
            "",
            "# Option 2: .mcp.json",
            json.dumps({root_key: {"kronode": server_config}}, indent=2),
        ]
        return "\n".join(lines)

    # Codex tool approvals (auto-approve all Kronode tools)
    TOOL_APPROVALS = """
[mcp_servers.kronode.tools.kronode_workflow]
approval_mode = "approve"

[mcp_servers.kronode.tools.get_context]
approval_mode = "approve"

[mcp_servers.kronode.tools.get_doc]
approval_mode = "approve"

[mcp_servers.kronode.tools.get_file_companions]
approval_mode = "approve"

[mcp_servers.kronode.tools.get_reviewer_guidance]
approval_mode = "approve"

[mcp_servers.kronode.tools.check_completeness]
approval_mode = "approve"
""".strip()

    # Special case: Codex uses TOML + CLI command
    if agent == "codex":
        if remote:
            lines = [
                f"# {info['name']} — {info['file']}",
                f"# {info['notes']}",
                "",
                "[mcp_servers.kronode]",
                f'url = "{url}/mcp/sse"',
                "",
                "[mcp_servers.kronode.headers]",
                f'Authorization = "Bearer {token}"',
                "",
                TOOL_APPROVALS,
            ]
        else:
            lines = [
                f"# {info['name']} — {info['file']}",
                f"# {info['notes']}",
                "",
                "[mcp_servers.kronode]",
                'command = "python"',
                f'args = ["-m", "app.mcp.main", "--token", "{token}"]',
                "",
                TOOL_APPROVALS,
            ]
        return "\n".join(lines)

    # Special case: Zed uses different structure
    if agent == "zed":
        zed_config = {
            root_key: {
                "kronode": {
                    "source": "custom",
                    "command": "python",
                    "args": ["-m", "app.mcp.main", "--token", token],
                    "env": {},
                }
            }
        }
        lines = [
            f"# {info['name']} — {info['file']}",
            f"# {info['notes']}",
            "",
            json.dumps(zed_config, indent=2),
        ]
        return "\n".join(lines)

    # Standard config
    config = {root_key: {"kronode": server_config}}
    lines = [
        f"# {info['name']} — {info['file']}",
        f"# {info['notes']}",
        "",
        json.dumps(config, indent=2),
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Kronode MCP Setup — generate configs for AI coding agents")
    parser.add_argument("agent", nargs="?", choices=list(AGENTS.keys()) + ["--all"],
                        help="Agent to generate config for")
    parser.add_argument("--all", action="store_true", help="Generate configs for all agents")
    parser.add_argument("--token", required=True, help="Kronode API token (kron_...)")
    parser.add_argument("--remote", action="store_true", help="Use HTTP transport (for remote/team deployment)")
    parser.add_argument("--url", default="https://api.kronode.dev", help="Kronode API URL (for remote)")
    parser.add_argument("--list", action="store_true", help="List all supported agents")
    args = parser.parse_args()

    if args.list:
        print("Supported AI coding agents:\n")
        for key, info in AGENTS.items():
            print(f"  {key:15s}  {info['name']}")
            print(f"  {'':15s}  Config: {info['file']}")
            print(f"  {'':15s}  Transports: {', '.join(info['transports'])}")
            print()
        return

    if args.all or args.agent == "--all":
        for key in AGENTS:
            print(f"\n{'=' * 60}")
            print(generate_config(key, args.token, args.remote, args.url))
        return

    if not args.agent:
        parser.print_help()
        sys.exit(1)

    print(generate_config(args.agent, args.token, args.remote, args.url))


if __name__ == "__main__":
    main()
