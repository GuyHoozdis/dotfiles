"""Host-safe lifecycle tests for the Tart shell fixture driver."""

import importlib.util
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

import pytest


DRIVER_PATH = Path(__file__).with_name("run_tart.py")
REQUIRED_SOURCES = {
    "etc/bash_profile.bash",
    "etc/bashrc.bash",
    "tests/shell/conftest.py",
    "tests/shell/scenarios.py",
    "tests/shell/probe.py",
    "tests/shell/test_bash.py",
    "tests/shell/test_dotfiles.py",
    "pyproject.toml",
    "uv.lock",
}


def load_driver():
    if not DRIVER_PATH.is_file():
        pytest.fail(f"Tart driver is not implemented: {DRIVER_PATH}")
    spec = importlib.util.spec_from_file_location("shell_tart_driver", DRIVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(self, *, pytest_status=0, clone_status=0, export_status=0):
        self.pytest_status = pytest_status
        self.clone_status = clone_status
        self.export_status = export_status
        self.commands = []
        self.stopped = False
        self.deleted = False
        self.clone_name = None
        self.malformed_list = False
        self.process = None
        self.tracked_sources = None

    def run(self, argv, **kwargs):
        self.commands.append((list(argv), kwargs))
        if argv[:2] == ["git", "ls-files"]:
            return subprocess.CompletedProcess(argv, 0, self.tracked_sources, b"")
        if argv[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(argv, 0, "abc123\n", "")
        if argv[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1] == "clone":
            self.clone_name = argv[3]
            return subprocess.CompletedProcess(argv, self.clone_status, "", "clone failed")
        if argv[1] == "exec":
            command = argv[3:]
            if command == ["/usr/bin/printf", "READY"]:
                return subprocess.CompletedProcess(argv, 0, "READY", "")
            if command[:2] == ["/bin/bash", "-lc"] and "command -v uv" in command[2]:
                return subprocess.CompletedProcess(argv, 1, "", "")
            if command[:2] == ["/bin/bash", "-c"] and " -x " in command[2]:
                return subprocess.CompletedProcess(argv, 0, "", "")
            if "pytest" in command:
                return subprocess.CompletedProcess(argv, self.pytest_status, "pytest output", "")
            if command[-1:] == ["--version"]:
                return subprocess.CompletedProcess(argv, 0, "uv 0.13.7\n", "")
            if command and command[0].endswith("tar") and "-cf" in command:
                if self.export_status:
                    return subprocess.CompletedProcess(argv, self.export_status, b"", b"export failed")
                return subprocess.CompletedProcess(argv, 0, result_archive(), b"")
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1] == "stop":
            self.stopped = True
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1] == "list":
            if self.malformed_list:
                return subprocess.CompletedProcess(argv, 0, json.dumps(self.malformed_list), "")
            state = "stopped" if self.stopped else "running"
            return subprocess.CompletedProcess(
                argv, 0, json.dumps([{"Name": self.clone_name, "State": state}]), ""
            )
        if argv[1] == "delete":
            self.deleted = True
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def popen(self, argv, **kwargs):
        self.process = FakeProcess()
        return self.process


class FakeProcess:
    returncode = None

    def __init__(self):
        self.wait_calls = 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.wait_calls += 1
        self.returncode = 0
        return self.returncode

    def terminate(self):
        self.returncode = 0


class StubbornProcess(FakeProcess):
    def __init__(self):
        super().__init__()
        self.terminate_calls = 0
        self.kill_calls = 0

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.wait_calls < 3:
            raise subprocess.TimeoutExpired("tart run", timeout)
        self.returncode = -9
        return self.returncode

    def terminate(self):
        self.terminate_calls += 1

    def kill(self):
        self.kill_calls += 1


def result_archive():
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        contents = b"<testsuite tests='1' failures='1' errors='0'/>"
        info = tarfile.TarInfo("results/pytest.xml")
        info.size = len(contents)
        archive.addfile(info, io.BytesIO(contents))
    return stream.getvalue()


def patch_runner(monkeypatch, driver, fake):
    fake.tracked_sources = subprocess.run(
        ["git", "ls-files", "-z", "--", *driver.SOURCE_FILES, "etc/bashrc.d/*.bash"],
        cwd=DRIVER_PATH.resolve().parents[2], check=True, capture_output=True,
    ).stdout
    monkeypatch.setattr(driver.subprocess, "run", fake.run)
    monkeypatch.setattr(driver.subprocess, "Popen", fake.popen)
    monkeypatch.setattr(driver, "fetch_locked_wheelhouse", lambda root: (b"wheelhouse", {}))


def run_driver(driver, argv):
    return driver.main(driver.parse_args(argv))


@pytest.mark.parametrize("suite", ["bash", "dotfiles"])
@pytest.mark.parametrize("marker", [None, "characterization", "acceptance"])
def test_parse_args_accepts_suites_and_optional_markers(suite, marker):
    argv = ["--image", "ubuntu", "--suite", suite, "--artifacts", "artifacts"]
    if marker:
        argv += ["--marker", marker]
    options = load_driver().parse_args(argv)
    assert options.suite == suite
    assert options.marker == marker


@pytest.mark.parametrize("extra", [[], ["--suite", "characterization"],
                                  ["--suite", "dotfiles", "--marker", "bash"]])
def test_parse_args_rejects_missing_or_invalid_choices(extra):
    with pytest.raises(SystemExit):
        load_driver().parse_args(["--image", "ubuntu", "--artifacts", "artifacts", *extra])


def test_failed_guest_suite_status_survives_collection_and_cleanup(tmp_path, monkeypatch):
    driver = load_driver()
    fake = FakeRunner(pytest_status=7)
    patch_runner(monkeypatch, driver, fake)
    artifacts = tmp_path / "artifacts"

    status = run_driver(driver, [
        "--image", "ubuntu", "--suite", "bash",
        "--artifacts", str(artifacts),
    ])

    metadata = json.loads((artifacts / "run.json").read_text())
    assert status == 7
    assert metadata["pytest_status"] == 7
    assert fake.stopped and fake.deleted
    assert (artifacts / "results/pytest.xml").is_file()


@pytest.mark.parametrize(
    "relative",
    ["etc/bash_profile.bash", "etc/bashrc.bash", "etc/bashrc.d/functions.bash"],
)
def test_source_archive_includes_startup_sources(relative):
    driver = load_driver()
    root = DRIVER_PATH.resolve().parents[2]
    archive_bytes, _ = driver.source_archive(root)

    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        assert relative in archive.getnames()
        member = archive.extractfile(relative)
        assert member is not None
        assert member.read() == (root / relative).read_bytes()


def test_source_archive_contains_tracked_modules_and_only_harness_sources():
    root = DRIVER_PATH.resolve().parents[2]
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "etc/bashrc.d/*.bash"],
        cwd=root, check=True, capture_output=True,
    ).stdout.decode().split("\0")
    modules = {name for name in tracked if name and not name.endswith(".local.bash")}
    archive_bytes, hashes = load_driver().source_archive(root)
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        assert set(archive.getnames()) == REQUIRED_SOURCES | modules
        assert set(hashes) == set(archive.getnames())


@pytest.fixture
def extracted_guest_source(tmp_path):
    root = DRIVER_PATH.resolve().parents[2]
    archive_bytes, _ = load_driver().source_archive(root)
    source = tmp_path / "source"
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        for member in archive:
            path = source / member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.extractfile(member).read())
    return source


@pytest.mark.parametrize("suite", ["bash", "dotfiles"])
def test_guest_source_suites_collect_without_legacy_startup(extracted_guest_source, suite):
    source = extracted_guest_source
    environment = {**os.environ, "PYTEST_ADDOPTS": "", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    result = subprocess.run(
        [
            sys.executable, "-I", "-B", "-m", "pytest", "--collect-only", "-q",
            f"tests/shell/test_{suite}.py", "--shell-bash", "/bin/bash",
            "--shell-guest-root", str(source.parent),
            "-o", f"cache_dir={source.parent / 'cache'}",
        ],
        cwd=source, env=environment, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_guest_source_dotfiles_fixture_works_without_git_checkout(extracted_guest_source):
    source = extracted_guest_source
    (source / "etc/bashrc.d/personal.local.bash").write_text("private\n")
    script = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "tests/shell"))
import conftest
class Factory:
    def mktemp(self, name):
        root = Path(sys.argv[1]) / name
        root.mkdir()
        return root
fixture = conftest._create_dotfiles_home("tracked", Factory(), Path("/bin/bash"))
assert set(fixture["modules"]) == {
    path.stem for path in (Path.cwd() / "etc/bashrc.d").glob("*.bash")
    if not path.name.endswith(".local.bash")
}
"""
    environment = {**os.environ, "GIT_CEILING_DIRECTORIES": str(source.parent)}
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(source.parent)],
        cwd=source, env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)


@pytest.fixture
def source_repo(tmp_path):
    root = tmp_path / "source-repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    paths = REQUIRED_SOURCES | {
        "etc/bashrc.d/current.bash",
        "etc/bashrc.d/committed.local.bash",
    }
    for relative in paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"initial {relative}\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "test sources"], cwd=root, check=True,
    )
    return root


def test_source_archive_discovers_new_committed_module_and_reads_worktree(source_repo):
    module = source_repo / "etc/bashrc.d/shell-options.bash"
    module.write_text("committed\n")
    subprocess.run(["git", "add", str(module)], cwd=source_repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "new module"], cwd=source_repo, check=True,
    )
    module.write_text("working tree\n")
    (source_repo / "etc/bashrc.d/personal.local.bash").write_text("private\n")
    (source_repo / "etc/bashrc.d/untracked.bash").write_text("untracked\n")
    (source_repo / "tests/shell/test_startup.py").write_text("legacy\n")

    data, hashes = load_driver().source_archive(source_repo)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        names = set(archive.getnames())
        assert names == REQUIRED_SOURCES | {
            "etc/bashrc.d/current.bash", "etc/bashrc.d/shell-options.bash",
        }
        assert archive.extractfile("etc/bashrc.d/shell-options.bash").read() == b"working tree\n"
        assert hashes["etc/bashrc.d/shell-options.bash"] == hashlib.sha256(b"working tree\n").hexdigest()


@pytest.mark.parametrize("state", ["missing", "untracked", "symlink"])
def test_source_archive_rejects_invalid_required_source(source_repo, state):
    driver = load_driver()
    path = source_repo / "tests/shell/probe.py"
    path.unlink()
    if state == "untracked":
        subprocess.run(["git", "rm", "--cached", "-q", str(path)], cwd=source_repo, check=True)
        path.write_text("untracked\n")
    elif state == "symlink":
        path.symlink_to("scenarios.py")
    with pytest.raises(driver.HarnessError, match="probe.py"):
        driver.source_archive(source_repo)


def test_source_archive_surfaces_git_errors(tmp_path, monkeypatch):
    driver = load_driver()
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nonexistent"))
    with pytest.raises(driver.HarnessError, match="git"):
        driver.source_archive(tmp_path)


def test_clone_failure_does_not_stop_or_delete_unowned_vm(tmp_path, monkeypatch):
    driver = load_driver()
    fake = FakeRunner(clone_status=1)
    patch_runner(monkeypatch, driver, fake)

    status = run_driver(driver, [
        "--image", "ubuntu", "--suite", "bash", "--artifacts", str(tmp_path / "artifacts"),
    ])

    assert status != 0
    assert not fake.stopped
    assert not fake.deleted
    assert not any(argv[1] in {"stop", "delete"} for argv, _ in fake.commands)


def test_artifact_failure_still_stops_and_deletes_owned_clone(tmp_path, monkeypatch):
    driver = load_driver()
    fake = FakeRunner(pytest_status=7, export_status=2)
    patch_runner(monkeypatch, driver, fake)

    status = run_driver(driver, [
        "--image", "ubuntu", "--suite", "bash", "--artifacts", str(tmp_path / "artifacts"),
    ])

    assert status != 0
    assert fake.stopped
    assert fake.deleted
    assert any(argv[1] == "stop" for argv, _ in fake.commands)
    assert any(argv[1] == "delete" for argv, _ in fake.commands)
    metadata = json.loads((tmp_path / "artifacts/run.json").read_text())
    assert metadata["pytest_status"] == 7


def test_unconfirmed_stop_retains_owned_clone(tmp_path, monkeypatch):
    driver = load_driver()
    fake = FakeRunner(export_status=2)
    original_run = fake.run

    def run(argv, **kwargs):
        result = original_run(argv, **kwargs)
        if argv[1] == "list" and fake.stopped:
            result.stdout = json.dumps([{"Name": fake.clone_name, "State": "running"}])
        return result

    fake.run = run
    patch_runner(monkeypatch, driver, fake)

    status = run_driver(driver, [
        "--image", "ubuntu", "--suite", "bash", "--artifacts", str(tmp_path / "artifacts"),
    ])

    metadata = json.loads((tmp_path / "artifacts/run.json").read_text())
    assert status != 0
    assert fake.stopped
    assert not fake.deleted
    assert fake.clone_name in metadata["cleanup_error"]


@pytest.mark.parametrize(
    ("archive_factory", "message"),
    [("without_junit", "missing"), ("invalid_junit", "invalid")],
)
def test_junit_artifact_must_exist_and_be_valid(tmp_path, archive_factory, message):
    driver = load_driver()
    archive = {
        "without_junit": result_archive_without_junit,
        "invalid_junit": result_archive_invalid_junit,
    }[archive_factory]()

    with pytest.raises(driver.HarnessError, match=message):
        driver.safe_extract_results(archive, tmp_path)
        driver.validate_junit_result(tmp_path)


def build_archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, kind, value in entries:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(value)
                archive.addfile(info, io.BytesIO(value))
                continue
            info.type = {
                "dir": tarfile.DIRTYPE,
                "symlink": tarfile.SYMTYPE,
                "hardlink": tarfile.LNKTYPE,
                "fifo": tarfile.FIFOTYPE,
            }[kind]
            info.linkname = value or ""
            archive.addfile(info)
    return stream.getvalue()


def test_result_symlinks_are_skipped_without_following(tmp_path):
    driver = load_driver()
    archive = build_archive([
        ("results", "dir", None),
        ("results/pytest.xml", "file", b"<testsuite/>"),
        ("results/pytest", "dir", None),
        ("results/pytest/scenariocurrent", "symlink", "/etc"),
    ])

    skipped = driver.safe_extract_results(archive, tmp_path)

    assert skipped == 1
    assert (tmp_path / "results/pytest.xml").is_file()
    link = tmp_path / "results/pytest/scenariocurrent"
    assert not link.exists() and not link.is_symlink()


@pytest.mark.parametrize(
    "entries",
    [
        [("results/link", "symlink", "elsewhere"), ("results/link/escape", "file", b"x")],
        [("results/link/escape", "file", b"x"), ("results/link", "symlink", "elsewhere")],
        [("results/link", "symlink", "a"), ("results/link", "symlink", "b")],
        [("../results/link", "symlink", "a")],
        [("results/hard", "hardlink", "results/pytest.xml")],
        [("results/pipe", "fifo", None)],
    ],
    ids=["nested-after", "nested-before", "duplicate", "unsafe-path", "hardlink", "fifo"],
)
def test_result_archive_rejects_unsafe_links_and_special_members(tmp_path, entries):
    driver = load_driver()

    with pytest.raises(driver.HarnessError):
        driver.safe_extract_results(build_archive(entries), tmp_path)

    assert not (tmp_path / "results").exists()


def test_skipped_result_symlinks_are_recorded_in_run_metadata(tmp_path, monkeypatch):
    driver = load_driver()
    fake = FakeRunner()
    original_run = fake.run

    def run(argv, **kwargs):
        result = original_run(argv, **kwargs)
        if argv[1] == "exec" and "-cf" in argv:
            result.stdout = build_archive([
                ("results/pytest.xml", "file", b"<testsuite/>"),
                ("results/pytest/scenariocurrent", "symlink", "scenario0"),
            ])
        return result

    fake.run = run
    patch_runner(monkeypatch, driver, fake)
    artifacts = tmp_path / "artifacts"

    status = run_driver(driver, ["--image", "ubuntu", "--suite", "bash", "--artifacts", str(artifacts)])

    metadata = json.loads((artifacts / "run.json").read_text())
    assert status == 0
    assert metadata["skipped_result_symlinks"] == 1


@pytest.mark.parametrize(
    ("image", "path", "interpreter"),
    [
        ("macos", "/opt/homebrew/bin/uv", "/opt/homebrew/bin/python3"),
        ("ubuntu", "/usr/local/bin/uv", "/usr/bin/python3"),
    ],
)
def test_existing_guest_uv_is_selected_without_bootstrap(monkeypatch, image, path, interpreter):
    driver = load_driver()
    commands = []

    def guest_command(log, clone, command, **kwargs):
        commands.append(command)
        if command[:2] == ["/bin/bash", "-lc"]:
            return subprocess.CompletedProcess(
                command, 0, f"startup output\n__DOTFILES_UV_PATH__{path}\n", ""
            )
        if command == [path, "--version"]:
            return subprocess.CompletedProcess(command, 0, "uv 0.9.0\n", "")
        raise AssertionError(f"unexpected guest command: {command}")

    monkeypatch.setattr(driver, "guest_command", guest_command)
    metadata = {}

    selected_interpreter, uv_path = driver.ensure_guest_uv(None, "clone", image, metadata)

    assert selected_interpreter == interpreter
    assert uv_path == path
    assert metadata["uv_path"] == uv_path
    assert metadata["uv_version"] == "uv 0.9.0"
    assert not any(command[:2] == [interpreter, "-c"] for command in commands)


def test_absent_guest_uv_is_bootstrapped_from_host_release_files(monkeypatch):
    driver = load_driver()
    asset = "uv-aarch64-unknown-linux-gnu.tar.gz"
    payload = b"pinned uv archive"
    digest = __import__("hashlib").sha256(payload).hexdigest()
    monkeypatch.setitem(driver.UV_ASSETS, "ubuntu", (asset, digest))
    metadata_bytes = f"{digest}  {asset}\n".encode()
    urls = []
    responses = [metadata_bytes, payload]

    class Response:
        def __init__(self, value):
            self.value = value

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return self.value

    def host_download(request, timeout):
        urls.append(request.full_url)
        return Response(responses.pop(0))

    monkeypatch.setattr(urllib.request, "urlopen", host_download)
    commands = []
    transferred = []

    def guest_command(log, clone, command, **kwargs):
        commands.append((command, kwargs))
        if command[:2] == ["/bin/bash", "-lc"]:
            return subprocess.CompletedProcess(command, 1, "", "")
        if command[:2] == ["/usr/bin/python3", "-c"]:
            transferred.append(kwargs.get("input_data"))
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ["/tmp/dotfiles-shell-harness/bin/uv", "--version"]:
            return subprocess.CompletedProcess(command, 0, "uv 0.13.7\n", "")
        raise AssertionError(f"unexpected guest command: {command}")

    monkeypatch.setattr(driver, "guest_command", guest_command)
    metadata = {}

    interpreter, uv_path = driver.ensure_guest_uv(None, "clone", "ubuntu", metadata)

    assert uv_path == "/tmp/dotfiles-shell-harness/bin/uv"
    assert metadata["uv_version"] == "uv 0.13.7"
    assert urls == [
        "https://github.com/astral-sh/uv/releases/download/0.13.7/sha256.sum",
        f"https://github.com/astral-sh/uv/releases/download/0.13.7/{asset}",
    ]
    assert len(transferred) == 1 and isinstance(transferred[0], bytes)
    with tarfile.open(fileobj=io.BytesIO(transferred[0]), mode="r:") as archive:
        assert set(archive.getnames()) == {"sha256.sum", asset}
        assert archive.extractfile("sha256.sum").read() == metadata_bytes
        assert archive.extractfile(asset).read() == payload
    bootstrap_command, bootstrap_options = next(
        (command, options)
        for command, options in commands
        if command[:2] == ["/usr/bin/python3", "-c"]
    )
    script = bootstrap_command[2]
    assert "sys.stdin.buffer.read()" in script
    assert "hashlib.sha256(payload).hexdigest()" in script
    assert "published != expected" in script
    assert "urllib" not in script
    assert bootstrap_options["timeout"] == 180


@pytest.mark.parametrize(
    ("reported", "accepted"),
    [
        ("uv 0.13.7 (316c827e0 2026-11-03 aarch64-apple-darwin)\n", True),
        ("uv 0.13.7\n", True),
        ("uv 0.13.70 (316c827e0 2026-11-03 aarch64-apple-darwin)\n", False),
        ("uv 0.13.7-rc1\n", False),
    ],
)
def test_bootstrapped_uv_version_matches_exact_pinned_release(monkeypatch, reported, accepted):
    driver = load_driver()

    def guest_command(log, clone, command, **kwargs):
        if command[:2] == ["/bin/bash", "-lc"]:
            return subprocess.CompletedProcess(command, 1, "", "")
        if command[:2] == ["/opt/homebrew/bin/python3", "-c"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ["/tmp/dotfiles-shell-harness/bin/uv", "--version"]:
            return subprocess.CompletedProcess(command, 0, reported, "")
        raise AssertionError(f"unexpected guest command: {command}")

    monkeypatch.setattr(driver, "guest_command", guest_command)
    monkeypatch.setattr(driver, "fetch_uv_bootstrap_bundle", lambda image: b"bundle")
    metadata = {}

    if accepted:
        driver.ensure_guest_uv(None, "clone", "macos", metadata)
        assert metadata["uv_version"] == "uv 0.13.7"
    else:
        with pytest.raises(driver.HarnessError, match="unexpected bootstrapped uv version"):
            driver.ensure_guest_uv(None, "clone", "macos", metadata)


def test_existing_guest_uv_with_build_metadata_is_selected(monkeypatch):
    driver = load_driver()

    def guest_command(log, clone, command, **kwargs):
        if command[:2] == ["/bin/bash", "-lc"]:
            return subprocess.CompletedProcess(
                command, 0, "__DOTFILES_UV_PATH__/opt/homebrew/bin/uv\n", ""
            )
        if command == ["/opt/homebrew/bin/uv", "--version"]:
            return subprocess.CompletedProcess(
                command, 0, "uv 0.9.0 (abc1234 2026-01-01 aarch64-apple-darwin)\n", ""
            )
        raise AssertionError(f"unexpected guest command: {command}")

    monkeypatch.setattr(driver, "guest_command", guest_command)
    metadata = {}

    _, uv_path = driver.ensure_guest_uv(None, "clone", "macos", metadata)

    assert uv_path == "/opt/homebrew/bin/uv"
    assert metadata["uv_version"] == "uv 0.9.0"


@pytest.mark.parametrize(("image", "timeout", "attempts"), [("macos", 600, 3), ("ubuntu", 180, 1)])
def test_guest_readiness_uses_image_specific_deadline(monkeypatch, image, timeout, attempts):
    driver = load_driver()
    now = [0]
    calls = []

    def guest_command(log, clone, command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 125, "", "guest is not ready")

    monkeypatch.setattr(driver, "guest_command", guest_command)
    monkeypatch.setattr(driver.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(driver.time, "sleep", lambda delay: now.__setitem__(0, now[0] + 200))
    monkeypatch.setattr(driver, "READINESS_INTERVAL", 200)

    with pytest.raises(driver.HarnessError, match=f"after {timeout}s"):
        driver.wait_for_guest(None, "clone", FakeProcess(), {"readiness_failures": []}, image)

    assert len(calls) == attempts


def test_guest_readiness_requires_output_sentinel(monkeypatch):
    driver = load_driver()
    calls = []
    responses = [
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, "READY", ""),
    ]

    def guest_command(log, clone, command, **kwargs):
        calls.append(command)
        return responses.pop(0)

    monkeypatch.setattr(driver, "guest_command", guest_command)
    monkeypatch.setattr(driver.time, "sleep", lambda delay: None)
    metadata = {"readiness_failures": []}

    driver.wait_for_guest(None, "clone", FakeProcess(), metadata, "macos")

    assert calls == [["/usr/bin/printf", "READY"]] * 2
    assert len(metadata["readiness_failures"]) == 1


def test_locked_wheelhouse_fetches_and_verifies_only_dev_wheels(tmp_path, monkeypatch):
    driver = load_driver()
    root = tmp_path / "source"
    root.mkdir()
    payloads = {
        "pytest-9.2.0-py3-none-any.whl": b"pytest wheel",
        "pluggy-1.7.0-py3-none-any.whl": b"pluggy wheel",
        "runtime-1.0-py3-none-any.whl": b"runtime wheel",
    }

    pytest_hash = hashlib.sha256(payloads["pytest-9.2.0-py3-none-any.whl"]).hexdigest()
    pluggy_hash = hashlib.sha256(payloads["pluggy-1.7.0-py3-none-any.whl"]).hexdigest()
    runtime_hash = hashlib.sha256(payloads["runtime-1.0-py3-none-any.whl"]).hexdigest()
    (root / "uv.lock").write_text(
        'version = 1\n'
        '[[package]]\nname = "tests"\nversion = "0.1"\n'
        'source = { virtual = "." }\n'
        'dependencies = [{ name = "runtime" }]\n'
        '[package.dev-dependencies]\ndev = [{ name = "pytest" }]\n'
        '[[package]]\nname = "pytest"\nversion = "9.2.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'dependencies = [{ name = "pluggy" }]\n'
        f'wheels = [{{ url = "https://files.pythonhosted.org/packages/pytest-9.2.0-py3-none-any.whl", hash = "sha256:{pytest_hash}" }}]\n'
        '[[package]]\nname = "pluggy"\nversion = "1.7.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        f'wheels = [{{ url = "https://files.pythonhosted.org/packages/pluggy-1.7.0-py3-none-any.whl", hash = "sha256:{pluggy_hash}" }}]\n'
        '[[package]]\nname = "runtime"\nversion = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        f'wheels = [{{ url = "https://files.pythonhosted.org/packages/runtime-1.0-py3-none-any.whl", hash = "sha256:{runtime_hash}" }}]\n'
    )
    requested = []

    class Response:
        def __init__(self, value):
            self.value = value

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return self.value

    def host_download(request, timeout):
        filename = Path(request.full_url).name
        requested.append(filename)
        return Response(payloads[filename])

    monkeypatch.setattr(urllib.request, "urlopen", host_download)

    archive_bytes, hashes = driver.fetch_locked_wheelhouse(root)

    assert requested == ["pluggy-1.7.0-py3-none-any.whl", "pytest-9.2.0-py3-none-any.whl"]
    assert hashes == {
        name: hashlib.sha256(payloads[name]).hexdigest()
        for name in requested
    }
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        assert set(archive.getnames()) == {
            f"wheelhouse/{name}" for name in requested
        }
        for name in requested:
            assert archive.extractfile(f"wheelhouse/{name}").read() == payloads[name]


def test_locked_wheelhouse_rejects_hash_mismatch(tmp_path, monkeypatch):
    driver = load_driver()
    root = tmp_path / "source"
    root.mkdir()
    (root / "uv.lock").write_text(
        'version = 1\n[[package]]\nname = "tests"\nversion = "0.1"\n'
        'source = { virtual = "." }\n[package.dev-dependencies]\n'
        'dev = [{ name = "pytest" }]\n[[package]]\nname = "pytest"\n'
        'version = "9.2.0"\nsource = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://files.pythonhosted.org/packages/pytest-py3-none-any.whl", '
        'hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000" }]\n'
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b"not the locked wheel"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: Response())

    with pytest.raises(driver.HarnessError, match="locked hash mismatch"):
        driver.fetch_locked_wheelhouse(root)


def test_offline_install_uses_locked_hashed_requirements_from_wheelhouse():
    driver = load_driver()
    root = "/tmp/dotfiles-shell-harness"

    assert driver.offline_install_commands("/bin/uv", "/usr/bin/python3") == [
        [
            "/bin/uv", "export", "--locked", "--offline", "--group", "dev",
            "--no-emit-project", "--format", "requirements.txt",
            "--output-file", f"{root}/requirements.txt",
        ],
        ["/bin/uv", "venv", "--offline", "--python", "/usr/bin/python3", f"{root}/venv"],
        [
            "/bin/uv", "pip", "install", "--offline", "--no-index",
            "--find-links", f"{root}/wheelhouse", "--require-hashes",
            "--python", f"{root}/venv/bin/python",
            "--requirement", f"{root}/requirements.txt",
        ],
    ]


@pytest.mark.parametrize(("suite", "marker"), [("bash", None), ("dotfiles", "acceptance")])
def test_guest_pytest_runs_from_offline_venv_without_sync(tmp_path, monkeypatch, suite, marker):
    driver = load_driver()
    fake = FakeRunner()
    patch_runner(monkeypatch, driver, fake)

    args = [
        "--image", "ubuntu", "--suite", suite,
        "--artifacts", str(tmp_path / "artifacts"),
    ]
    if marker:
        args += ["--marker", marker]
    status = run_driver(driver, args)

    guest = [argv[3:] for argv, _ in fake.commands if argv[:2] == ["tart", "exec"]]
    assert status == 0
    assert not any("sync" in command for command in guest)
    pytest_command = next(command for command in guest if "pytest" in command)
    assert pytest_command[5:8] == [
        "/tmp/dotfiles-shell-harness/venv/bin/python", "-m", "pytest",
    ]
    pytest_args = pytest_command[8:]
    assert f"tests/shell/test_{suite}.py" in pytest_args
    assert "-rs" in pytest_args
    if marker:
        assert pytest_args[pytest_args.index("-m") + 1] == marker
    else:
        assert "-m" not in pytest_args


@pytest.mark.parametrize("malformed", [{"wrong": "shape"}, [None]])
def test_malformed_vm_state_retains_clone_and_reaps_runner(tmp_path, monkeypatch, malformed):
    driver = load_driver()
    fake = FakeRunner(export_status=2)
    fake.malformed_list = malformed
    patch_runner(monkeypatch, driver, fake)

    status = run_driver(driver, [
        "--image", "ubuntu", "--suite", "bash", "--artifacts", str(tmp_path / "artifacts"),
    ])

    metadata = json.loads((tmp_path / "artifacts/run.json").read_text())
    assert status != 0
    assert not fake.deleted
    assert metadata["clone_retained"] == fake.clone_name
    assert "malformed" in metadata["cleanup_error"]
    assert fake.process.wait_calls > 0


def test_tart_runner_is_killed_and_reaped_after_terminate_timeout(tmp_path):
    driver = load_driver()
    process = StubbornProcess()
    stdout = tmp_path / "stdout"
    stderr = tmp_path / "stderr"
    stdout.write_text("")
    stderr.write_text("")
    runner_logs = {
        "record": {},
        "stdout_path": stdout,
        "stderr_path": stderr,
    }

    errors = driver.cleanup_clone(
        FakeCommandLog(tmp_path), None, process, runner_logs, {}
    )

    assert process.terminate_calls == 1
    assert process.kill_calls == 1
    assert process.wait_calls == 3
    assert not errors


def test_timed_out_text_command_preserves_partial_byte_output(monkeypatch, tmp_path):
    driver = load_driver()
    log = driver.CommandLog(tmp_path)

    def timeout_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(
            argv,
            kwargs["timeout"],
            output=b"partial stdout",
            stderr=b"partial stderr",
        )

    monkeypatch.setattr(driver.subprocess, "run", timeout_run)

    result = log.run(["guest-command"], timeout=1)

    assert result.returncode == 124
    assert result.stdout == "partial stdout"
    assert result.stderr == "partial stderr"
    assert log.records[0]["stdout"] == "partial stdout"
    assert log.records[0]["stderr"] == "partial stderr"


class FakeCommandLog:
    def __init__(self, path):
        self.path = path

    def run(self, *args, **kwargs):
        raise AssertionError("no Tart lifecycle command expected")


def result_archive_without_junit():
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        contents = b"observation"
        info = tarfile.TarInfo("results/observation.json")
        info.size = len(contents)
        archive.addfile(info, io.BytesIO(contents))
    return stream.getvalue()


def result_archive_invalid_junit():
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        contents = b"not xml"
        info = tarfile.TarInfo("results/pytest.xml")
        info.size = len(contents)
        archive.addfile(info, io.BytesIO(contents))
    return stream.getvalue()
