"""Kronode CLI — organizational memory for AI coding tools."""
import click


@click.group()
@click.version_option(version="0.2.0", prog_name="kronode")
def cli():
    """Kronode — extract team conventions from git history, serve via MCP."""
    pass


from kronode.cli.commands.init import init
from kronode.cli.commands.ingest import ingest
from kronode.cli.commands.serve import serve
from kronode.cli.commands.query import query
from kronode.cli.commands.setup import setup
from kronode.cli.commands.status import status
from kronode.cli.commands.add import add
from kronode.cli.commands.purge import purge

cli.add_command(init)
cli.add_command(ingest)
cli.add_command(serve)
cli.add_command(query)
cli.add_command(setup)
cli.add_command(status)
cli.add_command(add)
cli.add_command(purge)
