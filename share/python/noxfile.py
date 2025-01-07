"""Nox sessions."""

# https://nox.thea.codes/en/stable/config.html#modifying-nox-s-behavior-in-the-noxfile
import nox
from nox.sessions import Session

nox.options.sessions = "lint", "style", "mypy", "tests"
nox.options.stop_on_first_error = True
nox.options.error_on_external_run = True


DEFAULT_PYTHON_VERSION = "3.11"
SUPPORTED_PYTHON_VERSIONS = ["3.12", "3.11"]
SOURCE_CODE_TARGETS = ["src/", "tests/", "./noxfile.py"]


package = "prompt-llm-service"


@nox.session(python=DEFAULT_PYTHON_VERSION)
def mypy(session: Session) -> None:
    """Run static type checking using mypy."""
    args = session.posargs or SOURCE_CODE_TARGETS
    session.install("mypy", "nox")
    session.run("mypy", *args)


@nox.session(python=DEFAULT_PYTHON_VERSION)
def lint(session: Session) -> None:
    """Lint using ruff."""
    args = session.posargs or ["--fix", *SOURCE_CODE_TARGETS]
    session.install("ruff")
    session.run("ruff", "check", *args)


@nox.session(python=DEFAULT_PYTHON_VERSION)
def style(session: Session) -> None:
    """Apply style using ruff."""
    args = session.posargs or SOURCE_CODE_TARGETS
    session.install("ruff")
    session.run("ruff", "format", *args)


@nox.session(python=SUPPORTED_PYTHON_VERSIONS)
def tests(session: Session) -> None:
    """Run the test suite."""
    args = session.posargs or ["discover", "-s", "tests"]
    session.run("python", "-m", "unittest", *args)


@nox.session(python=DEFAULT_PYTHON_VERSION)
def coverage(session: Session) -> None:
    """Generate coverage report."""
    args = session.posargs or ["discover", "-s", "tests"]
    session.install("coverage[toml]")
    session.run("coverage", "erase")
    session.run("coverage", "run", "-m", "unittest", *args)
    session.run("coverage", "xml")
    session.run("coverage", "html")
    session.run("coverage", "report")
