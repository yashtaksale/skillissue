"""Build the files.json manifest from a WalkResult."""
from __future__ import annotations

import re
from pathlib import Path

from skillissue.pipeline.filter.types import FileInfo

# =====================================================================
# is_test patterns
# =====================================================================
_TEST_DIRS = {"test", "tests", "__tests__", "spec", "e2e", "integration"}

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

# =====================================================================
# is_config extensions
# =====================================================================
_CONFIG_EXTENSIONS = frozenset(
    {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}
)

# =====================================================================
# is_entrypoint patterns
# =====================================================================
_ENTRYPOINT_BASENAMES = {
    "main.py", "app.py", "wsgi.py", "asgi.py", "manage.py",
    "server.js", "server.ts", "index.js", "index.ts", "app.js", "app.ts",
}
_ENTRYPOINT_DIR_PARTS = {"pages", "api"}  # pages/api/**
_ENTRYPOINT_DIR_PARTS_APP = {"app", "api"}  # app/api/**
_ENTRYPOINT_DIR_ROUTES = "routes"

# =====================================================================
# risk_path_score patterns
# =====================================================================
_RISK_HIGH = re.compile(
    r"(?:^|/)(?:auth|login|logout|session|token|jwt|oauth|password|passwd|secret|crypto|payment|billing|stripe|admin|upload|download|sql|query|db|database|orm|middleware|permission|acl|rbac)(?:$|/)",
    re.IGNORECASE,
)
_RISK_MED = re.compile(
    r"(?:^|/)(?:api|route|router|controller|handler|view|endpoint|server|config|settings|webhook|shell|exec|process|template|render|deserial)(?:$|/)",
    re.IGNORECASE,
)


def _is_test(path: str) -> bool:
    """Check if path indicates a test file."""
    p = Path(path)
    # Check config files
    if p.name in _TEST_CONFIG_FILES:
        return True
    # Check directory segments
    parts = {part.casefold() for part in p.parts}
    if parts & _TEST_DIRS:
        return True
    # Check filename patterns
    name = p.name
    for pat in _TEST_FILE_PATTERNS:
        if pat.match(name):
            return True
    return False


def _is_config(path: str) -> bool:
    """Check if file is a configuration file."""
    p = Path(path)
    return p.suffix.lower() in _CONFIG_EXTENSIONS


def _is_entrypoint(path: str) -> bool:
    """Check if path is an application entrypoint."""
    p = Path(path)
    name = p.name
    if name in _ENTRYPOINT_BASENAMES:
        return True
    # Check for pages/api/ or app/api/ or routes/ in path
    parts = [part.casefold() for part in p.parts]
    if "pages" in parts and "api" in parts:
        return True
    if "app" in parts and "api" in parts:
        return True
    if _ENTRYPOINT_DIR_ROUTES in parts:
        return True
    return False


def _risk_path_score(path: str) -> float:
    """Compute risk_path_score based on path segments."""
    if _RISK_HIGH.search(path):
        return 1.0
    if _RISK_MED.search(path):
        return 0.5
    return 0.0


def build_manifest(files: list[FileInfo]) -> list[dict]:
    """Build a files.json manifest from FileInfo objects.

    Args:
        files: List of FileInfo objects from the walker.

    Returns:
        List of dicts with keys: path, lang, loc, bytes, sha1,
        is_test, is_config, is_entrypoint, risk_path_score.
    """
    manifest: list[dict] = []
    for f in files:
        entry: dict = {
            "path": f.path,
            "lang": f.lang,
            "loc": f.loc,
            "bytes": f.bytes,
            "sha1": f.sha1,
            "is_test": _is_test(f.path),
            "is_config": _is_config(f.path),
            "is_entrypoint": _is_entrypoint(f.path),
            "risk_path_score": _risk_path_score(f.path),
        }
        manifest.append(entry)
    return manifest
