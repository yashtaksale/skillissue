"""Hygiene checks (deterministic, from the file manifest only)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable


# =====================================================================
# Test detection
# =====================================================================
_TEST_DIRS = {"test", "tests", "__tests__", "spec", "e2e"}

_TEST_FILE_PATTERNS = [
    re.compile(r"^test_.*\.py$"),
    re.compile(r".*_test\.py$"),
    re.compile(r".*\.test\.(js|jsx|ts|tsx)$"),
    re.compile(r".*\.spec\.(js|jsx|ts|tsx)$"),
]

_TEST_CONFIG_FILES = {
    "pytest.ini", "tox.ini",
    "jest.config.js", "jest.config.ts", "jest.config.json",
    "vitest.config.js", "vitest.config.ts", "vitest.config.json",
    "playwright.config.js", "playwright.config.ts", "playwright.config.json",
}

_DEFAULT_TEST_SCRIPT = 'echo "Error: no test specified"'

# =====================================================================
# CI detection
# =====================================================================
_CI_PATTERNS = [
    re.compile(r"^\.github/workflows/[^/]+\.(yml|yaml)$"),
    re.compile(r"^\.gitlab-ci\.yml$"),
    re.compile(r"^\.circleci/config\.yml$"),
    re.compile(r"^azure-pipelines\.yml$"),
    re.compile(r"^Jenkinsfile$"),
    re.compile(r"^\.travis\.yml$"),
    re.compile(r"^bitbucket-pipelines\.yml$"),
]

# =====================================================================
# README detection
# =====================================================================
_README_NAMES = {"readme.md", "readme.rst", "readme.txt", "readme"}
_BADGE_PATTERN = re.compile(r"^!\[.*?\]\(.*?\)\s*$")

# =====================================================================
# License detection
# =====================================================================
_LICENSE_PATTERNS = [
    re.compile(r"^LICENSE(\..+)?$", re.IGNORECASE),
    re.compile(r"^LICENCE(\..+)?$", re.IGNORECASE),
    re.compile(r"^COPYING(\..+)?$", re.IGNORECASE),
]

# =====================================================================
# Linter/formatter config
# =====================================================================
_LINTER_PATTERNS = [
    re.compile(r"^\.eslintrc.*$"),
    re.compile(r"^eslint\.config\..*$"),
    re.compile(r"^\.prettierrc.*$"),
    re.compile(r"^prettier\.config\..*$"),
    re.compile(r"^biome\.json$"),
    re.compile(r"^ruff\.toml$"),
    re.compile(r"^\.ruff\.toml$"),
    re.compile(r"^\.flake8$"),
    re.compile(r"^\.pylintrc$"),
]
_RUFF_SECTION_RE = re.compile(r"^\[tool\.ruff\b", re.MULTILINE)
_BLACK_SECTION_RE = re.compile(r"^\[tool\.black\b", re.MULTILINE)
_FLAKE8_SECTION_RE = re.compile(r"^\[flake8\]", re.MULTILINE)

# =====================================================================
# Env file detection
# =====================================================================
_ENV_ALLOWED_SUFFIXES = (".example", ".sample", ".template", ".dist")
_ENV_BASE_NAMES = (".env", ".env.local", ".env.production",
                   ".env.development", ".env.staging", ".env.test",
                   ".env.production.local", ".env.development.local",
                   ".env.staging.local", ".env.test.local")

# =====================================================================
# Lockfile detection
# =====================================================================
_JS_LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "bun.lock", "bun.lockb",
}
_PY_LOCKFILES = {
    "poetry.lock", "Pipfile.lock", "uv.lock", "pdm.lock",
}


# =====================================================================
# Public entry point
# =====================================================================


def _normalize(path: str) -> str:
    """Normalize path separators."""
    return path.replace("\\", "/")


def _root_files(root_paths: Iterable[str]) -> set[str]:
    """Get the set of root-level filenames (case-folded)."""
    return {
        Path(p).name.casefold()
        for p in root_paths
        if "/" not in _normalize(p) and "\\" not in _normalize(p)
    }


def _all_paths(all_paths: Iterable[str]) -> list[str]:
    return [_normalize(p) for p in all_paths]


def _is_test_path(path: str, *, full_paths: set[str]) -> bool:
    p = Path(_normalize(path))
    if p.name in _TEST_CONFIG_FILES:
        return True
    if p.name.casefold() in _TEST_CONFIG_FILES:
        return True
    parts = {part.casefold() for part in p.parts}
    if parts & _TEST_DIRS:
        return True
    name = p.name
    for pat in _TEST_FILE_PATTERNS:
        if pat.match(name):
            return True
    return False


def _package_json_test_present(repo_root: Path) -> bool:
    pkg = repo_root / "package.json"
    if not pkg.is_file():
        return False
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return False
    test_script = scripts.get("test")
    if not isinstance(test_script, str):
        return False
    return test_script.strip() != _DEFAULT_TEST_SCRIPT


def _has_ci(all_p: list[str]) -> bool:
    for p in all_p:
        np = _normalize(p)
        for pat in _CI_PATTERNS:
            if pat.match(np):
                return True
    return False


def _has_readme(root_set: set[str], repo_root: Path) -> tuple[bool, str | None]:
    for name in root_set:
        if name in _README_NAMES:
            # Found by case-folded name; find actual path
            actual = None
            for candidate in ["README.md", "README.rst", "README.txt", "README"]:
                if candidate.casefold() == name and (repo_root / candidate).is_file():
                    actual = candidate
                    break
            if actual is None:
                # try other root files
                for f in repo_root.iterdir():
                    if f.name.casefold() == name:
                        actual = f.name
                        break
            if actual is not None:
                return True, actual
    return False, None


def _has_license(root_set: set[str], repo_root: Path) -> bool:
    for name in root_set:
        for pat in _LICENSE_PATTERNS:
            if pat.match(name):
                # verify file exists at root
                # Iterate the dir to find matching file
                for f in repo_root.iterdir():
                    if pat.match(f.name.casefold()):
                        return True
    return False


def _has_license_in_metadata(repo_root: Path) -> bool:
    pkg = repo_root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("license"):
                return True
        except (OSError, json.JSONDecodeError):
            pass
    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8").lower()
            if "[project]" in content and "license" in content:
                # Crude check: "[project]\n... license = ..." somewhere
                if re.search(r"license\s*=", content):
                    return True
        except OSError:
            pass
    return False


def _has_gitignore(root_set: set[str]) -> bool:
    return ".gitignore" in root_set


def _has_lockfile(all_p: list[str], root_set: set[str], repo_root: Path) -> bool:
    # JS lockfiles
    for lock in _JS_LOCKFILES:
        if lock.casefold() in root_set:
            return True
    # Python lockfiles
    for lock in _PY_LOCKFILES:
        if lock.casefold() in root_set:
            return True
    # requirements*.txt where >= 80% of lines use ==
    pyproject = repo_root / "pyproject.toml"
    pipfile = repo_root / "Pipfile"
    has_py_deps = pyproject.is_file() or pipfile.is_file()
    if not has_py_deps:
        for name in root_set:
            if name.startswith("requirements") and name.endswith(".txt"):
                has_py_deps = True
                break
    if has_py_deps:
        for name in root_set:
            if name.startswith("requirements") and name.endswith(".txt"):
                f = repo_root / name
                if f.is_file():
                    try:
                        lines = [
                            ln.strip()
                            for ln in f.read_text(encoding="utf-8").splitlines()
                            if ln.strip() and not ln.strip().startswith("#")
                        ]
                    except OSError:
                        continue
                    if not lines:
                        continue
                    pinned = sum(1 for ln in lines if "==" in ln)
                    if pinned / len(lines) >= 0.8:
                        return True
    return False


def _has_linter(all_p: list[str], root_set: set[str], repo_root: Path) -> bool:
    for p in all_p:
        np = _normalize(p)
        for pat in _LINTER_PATTERNS:
            if pat.match(Path(np).name.casefold()):
                # verify root
                if "/" not in np and "\\" not in np:
                    return True
    # pyproject.toml containing [tool.ruff, [tool.black, or setup.cfg [flake8]
    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8")
        except OSError:
            content = ""
        if _RUFF_SECTION_RE.search(content) or _BLACK_SECTION_RE.search(content):
            return True
    setup_cfg = repo_root / "setup.cfg"
    if setup_cfg.is_file():
        try:
            content = setup_cfg.read_text(encoding="utf-8")
        except OSError:
            content = ""
        if _FLAKE8_SECTION_RE.search(content):
            return True
    return False


def _has_env_committed(all_p: list[str]) -> bool:
    for p in all_p:
        np = _normalize(p)
        # Only consider root-level env files
        if "/" in np or "\\" in np:
            continue
        name = Path(np).name
        if not any(name == base for base in _ENV_BASE_NAMES):
            continue
        # Skip if has allowed suffix
        if any(name.endswith(suf) for suf in _ENV_ALLOWED_SUFFIXES):
            continue
        return True
    return False


def check(
    all_paths: list[str],
    repo_root: Path | str,
    *,
    skip_package_json_check: bool = False,
) -> list[str]:
    """Run all 9 hygiene checks and return flag strings.

    Args:
        all_paths: All relative paths in the repo (including ignored ones
            for completeness; manifest-based filtering also fine).
        repo_root: Absolute path to the extracted repo on disk.
        skip_package_json_check: Skip the package.json test-script check
            (used when package.json isn't read for some reason).

    Returns:
        List of hygiene flag strings (e.g. "no_tests", "no_ci", ...).
    """
    repo_root = Path(repo_root)
    normalized = _all_paths(all_paths)
    root_set = _root_files(all_paths)

    flags: list[str] = []

    # 1. Tests
    has_test_path = any(_is_test_path(p, full_paths=set(normalized)) for p in normalized)
    has_test_script = False if skip_package_json_check else _package_json_test_present(repo_root)
    if not (has_test_path or has_test_script):
        flags.append("no_tests")

    # 2. CI
    if not _has_ci(normalized):
        flags.append("no_ci")

    # 3. README (with thin-readme check)
    has_readme, readme_name = _has_readme(root_set, repo_root)
    if not has_readme:
        flags.append("no_readme")
    else:
        # Check if readme is "thin" (only badges, very short, or all badges)
        is_thin = _is_thin_readme(repo_root, readme_name) if readme_name else True
        if is_thin:
            flags.append("thin_readme")

    # 4. License
    has_license_file = _has_license(root_set, repo_root)
    has_license_meta = _has_license_in_metadata(repo_root)
    if not (has_license_file or has_license_meta):
        flags.append("no_license")

    # 5. .gitignore
    if not _has_gitignore(root_set):
        flags.append("no_gitignore")

    # 6. Lockfile
    if not _has_lockfile(normalized, root_set, repo_root):
        flags.append("no_lockfile")

    # 7. Linter/formatter config
    if not _has_linter(normalized, root_set, repo_root):
        flags.append("no_linter")

    # 8. Committed env file
    if _has_env_committed(normalized):
        flags.append("env_committed")

    return flags


def _is_thin_readme(repo_root: Path, name: str) -> bool:
    """A README is 'thin' if it is mostly badges or very short."""
    f = repo_root / name
    if not f.is_file():
        return True
    try:
        content = f.read_text(encoding="utf-8")
    except OSError:
        return True
    stripped_lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    if len(stripped_lines) < 5:
        return True
    badge_lines = sum(1 for ln in stripped_lines if _BADGE_PATTERN.match(ln))
    return badge_lines >= len(stripped_lines) - 1 and len(stripped_lines) < 20
