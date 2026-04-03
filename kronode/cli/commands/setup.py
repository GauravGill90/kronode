"""kronode setup — print MCP config for AI coding tools."""
import click
from rich.console import Console
from rich.syntax import Syntax

console = Console()

AGENTS = {
    "claude-code": ("Claude Code", '{\n  "mcpServers": {\n    "kronode": {\n      "command": "kronode",\n      "args": ["serve"]\n    }\n  }\n}', ".mcp.json"),
    "cursor": ("Cursor", '{\n  "mcpServers": {\n    "kronode": {\n      "command": "kronode",\n      "args": ["serve"]\n    }\n  }\n}', ".cursor/mcp.json"),
    "copilot": ("GitHub Copilot", '{\n  "servers": {\n    "kronode": {\n      "command": "kronode",\n      "args": ["serve"]\n    }\n  }\n}', ".vscode/mcp.json"),
    "codex": ("OpenAI Codex", '[mcp_servers.kronode]\ncommand = "kronode"\nargs = ["serve"]\n\n[mcp_servers.kronode.tools.get_context]\napproval_mode = "approve"\n\n[mcp_servers.kronode.tools.get_doc]\napproval_mode = "approve"', "~/.codex/config.toml"),
    "windsurf": ("Windsurf", '{\n  "mcpServers": {\n    "kronode": {\n      "command": "kronode",\n      "args": ["serve"]\n    }\n  }\n}', "~/.codeium/windsurf/mcp_config.json"),
    "zed": ("Zed", '{\n  "context_servers": {\n    "kronode": {\n      "source": "custom",\n      "command": "kronode",\n      "args": ["serve"]\n    }\n  }\n}', "settings.json"),
    "continue": ("Continue", '{\n  "mcpServers": {\n    "kronode": {\n      "command": "kronode",\n      "args": ["serve"]\n    }\n  }\n}', ".continue/mcpServers/kronode.json"),
}


@click.command()
@click.argument("agent", required=False, type=click.Choice(list(AGENTS.keys())))
@click.option("--list", "list_agents", is_flag=True, help="List all supported agents")
def setup(agent: str | None, list_agents: bool):
    """Print MCP config for your AI coding tool.

    Example: kronode setup claude-code
    """
    if list_agents or not agent:
        console.print("\n[bold]Supported AI tools:[/bold]\n")
        for key, (name, _, config_file) in AGENTS.items():
            console.print(f"  [cyan]{key:15s}[/cyan] {name} ({config_file})")
        console.print(f"\nUsage: [cyan]kronode setup <tool>[/cyan]\n")
        return

    name, config, config_file = AGENTS[agent]

    console.print(f"\n[bold]{name}[/bold] — add to [cyan]{config_file}[/cyan]:\n")

    if agent == "claude-code":
        console.print("Option 1: CLI command")
        console.print("[cyan]claude mcp add kronode -- kronode serve[/cyan]\n")
        console.print("Option 2: .mcp.json")

    lang = "toml" if agent == "codex" else "json"
    console.print(Syntax(config, lang, theme="monokai"))
    console.print()
