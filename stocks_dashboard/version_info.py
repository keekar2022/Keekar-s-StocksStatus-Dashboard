# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Read build version from generated _version.py or local git fallback."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_URL = "https://github.com/keekar2022/Keekar-s-StocksStatus-Dashboard"
_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class VersionInfo:
    version: str
    git_sha: str
    git_branch: str
    build_time_utc: str
    repo_url: str
    commit_url: str


def _git_fallback(field: str) -> str:
    try:
        if field == "sha_short":
            return subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=_ROOT,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        if field == "sha_full":
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=_ROOT,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        if field == "branch":
            return subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=_ROOT,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return ""


def get_version_info() -> VersionInfo:
    try:
        from stocks_dashboard import _version as v  # noqa: WPS433

        return VersionInfo(
            version=v.__version__,
            git_sha=v.__git_sha__,
            git_branch=v.__git_branch__,
            build_time_utc=v.__build_time_utc__,
            repo_url=v.__repo_url__,
            commit_url=v.__commit_url__,
        )
    except ImportError:
        sha_full = _git_fallback("sha_full")
        sha_short = _git_fallback("sha_short") or "local"
        branch = _git_fallback("branch") or "dev"
        build_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        date_part = build_time[:10].replace("-", ".")
        version = f"{date_part}+{sha_short}" if sha_short != "local" else "dev-local"
        commit_url = f"{REPO_URL}/commit/{sha_full}" if sha_full else REPO_URL
        return VersionInfo(
            version=version,
            git_sha=sha_short,
            git_branch=branch,
            build_time_utc=build_time,
            repo_url=REPO_URL,
            commit_url=commit_url,
        )


def format_build_time(iso_utc: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso_utc


def footer_markdown(info: VersionInfo | None = None) -> str:
    v = info or get_version_info()
    built = format_build_time(v.build_time_utc)
    return (
        f"{v.version} · **{v.git_branch}** · built {built} · "
        f"[View commit on GitHub]({v.commit_url})"
    )
