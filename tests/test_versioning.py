"""Verify real build metadata against disposable Git histories."""

from email.parser import BytesParser
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

from packaging.version import Version
import pytest


ROOT = Path(__file__).resolve().parents[1]


def run(directory, *args):
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_AUTHOR_NAME": "Version test",
        "GIT_AUTHOR_EMAIL": "version-test@example.invalid",
        "GIT_COMMITTER_NAME": "Version test",
        "GIT_COMMITTER_EMAIL": "version-test@example.invalid",
    }
    # A caller's CI override must not hide what these test Git histories say.
    for key in list(env):
        if key.startswith("SETUPTOOLS_SCM_PRETEND_"):
            del env[key]
    return subprocess.run(
        args, cwd=directory, env=env, check=True, capture_output=True, text=True,
    )


@pytest.fixture
def project(tmp_path):
    directory = tmp_path / "project"
    directory.mkdir()
    for name in (
        "pyproject.toml", "README.md", ".gitignore", ".mdformat.toml",
        ".pre-commit-config.yaml",
    ):
        shutil.copy2(ROOT / name, directory / name)
    shutil.copytree(
        ROOT / "src", directory / "src", ignore=shutil.ignore_patterns("__pycache__"),
    )
    run(directory, "git", "init", "--initial-branch=main")
    run(directory, "git", "add", ".")
    run(directory, "git", "commit", "-m", "[test] Initialize version fixture")
    return directory


def build(directory, target):
    output = directory / ".ocs" / "dist"
    output.mkdir(parents=True, exist_ok=True)
    result = run(
        directory, sys.executable, "-B", "-c",
        f"from hatchling.build import build_{target}; print(build_{target}({str(output)!r}))",
    )
    return output / result.stdout.strip().splitlines()[-1]


def wheel_version(path):
    with zipfile.ZipFile(path) as archive:
        metadata_path = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = BytesParser().parsebytes(archive.read(metadata_path))
    return Version(metadata["Version"])


def test_clean_tag_is_release_version(project):
    run(project, "git", "tag", "v1.2.3")
    assert wheel_version(build(project, "wheel")) == Version("1.2.3")


def test_commits_after_tag_get_next_patch_development_version(project):
    run(project, "git", "tag", "v1.2.3")
    with (project / "README.md").open("a") as stream:
        stream.write("\nA development change.\n")
    run(project, "git", "add", "README.md")
    run(project, "git", "commit", "-m", "[test] Advance version fixture")
    version = wheel_version(build(project, "wheel"))
    assert version.public == "1.2.4.dev1"
    assert version.local.startswith("g")


def test_dirty_checkout_has_development_version_and_date(project):
    run(project, "git", "tag", "v1.2.3")
    with (project / "README.md").open("a") as stream:
        stream.write("\nAn uncommitted change.\n")
    version = wheel_version(build(project, "wheel"))
    assert version.public == "1.2.4.dev0"
    assert version.local.startswith("g")
    assert ".d" in version.local


def test_untagged_checkout_gets_development_version(project):
    assert wheel_version(build(project, "wheel")).is_devrelease


def test_sdist_preserves_release_version_without_git(project, tmp_path):
    run(project, "git", "tag", "v1.2.3")
    archive_path = build(project, "sdist")
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with tarfile.open(archive_path) as archive:
        if hasattr(tarfile, "data_filter"):
            archive.extractall(extracted, filter="data")
        else:
            # Python < 3.12 without the filter backport: this archive was built
            # from our own fixture just above, rather than external input.
            archive.extractall(extracted)
    source = next(extracted.iterdir())
    assert not (source / ".git").exists()
    assert wheel_version(build(source, "wheel")) == Version("1.2.3")
