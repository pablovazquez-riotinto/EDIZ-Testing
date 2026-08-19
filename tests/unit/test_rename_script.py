import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT))

from rename_script import (  # noqa: E402
    Command,
    Rename,
    Replace,
    State,
    main,
    run_commands,
)


class Error(Command):
    def execute(self):
        raise Exception("Failed to execute")

    def rollback(self):
        pass


def test_state_from_files(tmpdir):
    """State from files should read from pyproject.toml and CODEOWNERS."""
    pyproject = tmpdir / "pyproject.toml"
    pyproject.write(dedent("""\
        [tool.hatch.build.targets.wheel]
        packages = ["foo/bar"]
        """))
    codeowners = tmpdir / "CODEOWNERS"
    codeowners.write("* @baz")
    state = State.from_files(pyproject, codeowners)
    assert state == State("foo", "bar", "baz")


@pytest.mark.parametrize(
    "content",
    [
        "",
        dedent("""\
            [tool.hatch.build.targets.wheel]
            packages = [
            ]
        """),
        dedent("""\
            [tool.hatch.build.targets.wheel]
            packages = ["foo"]
        """),
    ],
)
def test_state_from_files_pyproject_error(content, tmpdir):
    """State from files should raise if pyproject.toml is invalid."""
    pyproject = tmpdir / "pyproject.toml"
    pyproject.write(content)
    codeowners = tmpdir / "CODEOWNERS"
    codeowners.write("* @baz")
    with pytest.raises(ValueError):
        State.from_files(pyproject, codeowners)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "* foo",
    ],
)
def test_state_from_files_codeowners_error(content, tmpdir):
    """State from files should raise if CODEOWNERS is invalid."""
    pyproject = tmpdir / "pyproject.toml"
    pyproject.write(dedent("""\
        [tool.hatch.build.targets.wheel]
        packages = ["foo/bar"]
        """))
    codeowners = tmpdir / "CODEOWNERS"
    codeowners.write(content)
    with pytest.raises(ValueError):
        State.from_files(pyproject, codeowners)


@patch("rename_script.input")
def test_state_from_input(mock_input):
    """State from user input should split the input on hyphens."""
    mock_input.return_value = "foo-bar"
    state = State.from_input()
    assert state == State("foo", "bar", "foo-bar")


@patch("rename_script.run")
def test_rename(mock_run):
    """Renaming should execute and rollback correctly."""
    command = Rename("old", "new")
    command.execute()
    mock_run.asssert_called_once(["git", "mv", "old", "new"])
    command.rollback()
    mock_run.asssert_called_once(["git", "mv", "new", "old"])


def test_replace(tmpdir):
    """Replacing text should execute and rollback correctly."""
    path = tmpdir.join("path")
    path.write("old")
    command = Replace("old", "new", path)
    assert path.read() == "old"
    command.execute()
    assert path.read() == "new"
    command.rollback()
    assert path.read() == "old"


def test_error():
    """The error command should raise when executed."""
    with pytest.raises(Exception):  # noqa: B017
        Error().execute()


def test_run_commands_success(tmpdir):
    """Running commands should execute all commands."""
    path = tmpdir.join("path")
    path.write("old")

    commands = [
        Replace("old", "new", path),
        Replace("new", "newer", path),
    ]
    run_commands(commands)
    assert path.read() == "newer"


def test_run_commands_error(tmpdir):
    """Running commands should rollback if any fails."""
    path = tmpdir.join("path")
    path.write("old")

    commands = [
        Replace("old", "new", path),
        Replace("new", "newer", path),
        Error(),
    ]
    with pytest.raises(Exception):  # noqa: B017
        run_commands(commands)
    assert path.read() == "old"


@patch("rename_script.run_commands")
def test_main(mock_run_commands):
    """The main function should run commands when given a project name and owner."""
    main(["--name", "foo-bar", "--owner", "baz"])
    mock_run_commands.assert_called_once()


@patch("sys.stdout")
def test_main_help(stdout):
    """The main function should output usage when asked for --help."""
    with pytest.raises(SystemExit):
        main(["--help"])

    assert "usage" in stdout.write.call_args[0][0]
