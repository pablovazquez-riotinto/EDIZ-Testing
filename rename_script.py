import argparse
import logging
import re
import sys
import tomllib as toml
from abc import ABC, abstractmethod
from pathlib import Path
from subprocess import run


class State:
    def __init__(self, namespace, package, owner):
        self.namespace = namespace
        self.package = package
        self.owner = owner

    def __eq__(self, other):
        return self.namespace == other.namespace and self.package == other.package and self.owner == other.owner

    @classmethod
    def from_files(cls, pyproject="pyproject.toml", codeowners=".github/CODEOWNERS"):
        """Get the old state from the pyproject.toml and CODEOWNERS files."""
        with open(pyproject, "rb") as f:
            data = toml.load(f)

        packages = data.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {}).get("packages", [])
        if not packages:
            raise ValueError("No package information found in pyproject.toml.")

        include = packages[0]

        try:
            namespace, package = Path(include).parts
        except ValueError:
            raise ValueError(
                f"Unexpected package structure in pyproject.toml: {include}. Expected '<namespace>/<package>'."
            ) from None

        contents = Path(codeowners).read_text()

        # https://github.com/shinnn/github-username-regex#githubusernameregex
        GITHUB_USERNAME_REGEX = r"[A-Za-z\d](?:[A-Za-z\d]|-(?=[A-Za-z\d])){0,38}"
        m = re.search(f"@(?P<username>{GITHUB_USERNAME_REGEX})", contents)
        if not m:
            raise ValueError(f"No valid owner found in {codeowners}!")

        owner = m.group("username")

        return cls(namespace, package, owner)

    @classmethod
    def from_input(cls, name=None, owner=None):
        """Get the new state from user input."""
        while True:
            if not name:
                name = input("Please enter the project name in the format '<department>-<project>' (e.g., rtft-agni): ")
            try:
                namespace, package = name.split("-")
                break
            except ValueError:  # pragma: no cover
                logging.error("Invalid format! Please ensure the format is '<department>-<project>'.❌")  # noqa: TRY400
                name = None

        if not owner:
            owner = input("Please enter the project owner's GitHub username (without @), (e.g., rio-marc): ")

        return cls(namespace, package, owner)


class Command(ABC):
    @abstractmethod
    def execute(self):
        """Execute the command."""

    @abstractmethod
    def rollback(self):
        """Rollback the command."""


class Rename(Command):
    """
    Rename a file or directory using 'git mv' to maintain Git history.

    :param source: Path to the existing file or directory
    :param destination: Desired new path for the file or directory
    """

    def __init__(self, source, destination, root="."):
        self.source = Path(root) / source
        self.destination = Path(root) / destination

    def execute(self):
        """Execute renaming of a file or directory using 'git mv' to maintain Git history."""
        run(["git", "mv", str(self.source), str(self.destination)])  # noqa: S603 S607

    def rollback(self):
        """Rollback renaming of a file or directory using 'git mv' to maintain Git history."""
        run(["git", "mv", str(self.destination), str(self.source)])  # noqa: S603 S607


class Replace(Command):
    """
    Replace text in a file.

    :param path: Path to the file where text needs to be replaced
    :param old_text: Text to be replaced
    :param new_text: Text to replace with
    """

    def __init__(self, old_text, new_text, path):
        self.old_text = old_text
        self.new_text = new_text
        self.path = Path(path)

    def execute(self):
        """Execute replacing text in a file."""
        old_text = self.path.read_text(encoding="utf-8")
        new_text = old_text.replace(self.old_text, self.new_text)
        self.path.write_text(new_text, encoding="utf-8")

    def rollback(self):
        """Rollback replacing text in a file."""
        old_text = self.path.read_text(encoding="utf-8")
        new_text = old_text.replace(self.new_text, self.old_text)
        self.path.write_text(new_text, encoding="utf-8")


def run_commands(commands):
    """Run a list of commands and rollback if any fails."""
    if not commands:
        return

    command, *remaining = commands
    command.execute()
    try:
        run_commands(remaining)
    except Exception:
        command.rollback()
        raise


def rename_commands(old, new):
    """Make the commands for renaming `old` to `new`."""
    sources = [
        "docs/conf.py",
        "pyproject.toml",
    ]

    return [
        *[Replace(old.namespace, new.namespace, s) for s in sources],
        *[Replace(old.package, new.package, s) for s in sources],
        Replace(f"@{old.owner}", f"@{new.owner}", ".github/CODEOWNERS"),
        Rename(old.package, new.package, root=old.namespace),
        Rename(old.namespace, new.namespace),
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Set the logging level.")
    parser.add_argument(
        "--name",
        help="name of project name",
    )
    parser.add_argument(
        "--owner",
        help="owner of the project",
    )
    parser.add_argument(
        "--log-level",
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="log level (default %(default)s)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level)

    new = State.from_input(args.name, args.owner)
    old = State.from_files()
    commands = rename_commands(old, new)
    run_commands(commands)


if __name__ == "__main__":  # pragma: no cover
    try:
        main()
    except KeyboardInterrupt:
        logging.exception("User interrupted the process. Exiting!")
        sys.exit(1)
    except Exception:
        logging.exception("An unexpected error occurred. Exiting!")
        sys.exit(1)
