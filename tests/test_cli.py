from typer.testing import CliRunner

from labgate import __version__
from labgate.cli import app


def test_version():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"labgate {__version__}"


def test_init_is_a_subcommand():
    result = CliRunner().invoke(app, ["init", "--help"])
    assert result.exit_code == 0
