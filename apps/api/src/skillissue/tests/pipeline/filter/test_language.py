"""Tests for language detection (T-2.2)."""
from __future__ import annotations

import os
import tempfile

import pytest

from skillissue.pipeline.filter.language import detect


class TestDetectLanguage:
    def test_python_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "python"
        finally:
            os.unlink(path)

    def test_javascript_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "javascript"
        finally:
            os.unlink(path)

    def test_typescript_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "typescript"
        finally:
            os.unlink(path)

    def test_tsx_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".tsx", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "javascript"
        finally:
            os.unlink(path)

    def test_go_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".go", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "go"
        finally:
            os.unlink(path)

    def test_rust_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".rs", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "rust"
        finally:
            os.unlink(path)

    def test_ruby_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".rb", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "ruby"
        finally:
            os.unlink(path)

    def test_php_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".php", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "php"
        finally:
            os.unlink(path)

    def test_csharp_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".cs", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "csharp"
        finally:
            os.unlink(path)

    def test_cpp_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".cpp", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "cpp"
        finally:
            os.unlink(path)

    def test_case_insensitive(self):
        with tempfile.NamedTemporaryFile(suffix=".PY", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "python"
        finally:
            os.unlink(path)

    def test_unknown_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            assert detect(path) == "unknown"
        finally:
            os.unlink(path)

    def test_dockerfile_no_extension(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "Dockerfile")
        with open(path, "wb") as f:
            f.write(b"FROM python:3.12\n")
        try:
            assert detect(path) == "dockerfile"
        finally:
            os.unlink(path)
            os.rmdir(d)

    def test_shebang_python(self):
        with tempfile.NamedTemporaryFile(suffix="", delete=False) as f:
            f.write(b"#!/usr/bin/env python3\n")
            path = f.name
        try:
            assert detect(path, b"#!/usr/bin/env python3\n") == "python"
        finally:
            os.unlink(path)

    def test_shebang_bash(self):
        with tempfile.NamedTemporaryFile(suffix="", delete=False) as f:
            f.write(b"#!/bin/bash\n")
            path = f.name
        try:
            assert detect(path, b"#!/bin/bash\n") == "shell"
        finally:
            os.unlink(path)

    def test_shebang_node(self):
        with tempfile.NamedTemporaryFile(suffix="", delete=False) as f:
            f.write(b"#!/usr/bin/env node\n")
            path = f.name
        try:
            assert detect(path, b"#!/usr/bin/env node\n") == "javascript"
        finally:
            os.unlink(path)

    def test_no_shebang_no_ext_unknown(self):
        with tempfile.NamedTemporaryFile(suffix="", delete=False) as f:
            f.write(b"hello\n")
            path = f.name
        try:
            assert detect(path) == "unknown"
        finally:
            os.unlink(path)

    def test_content_head_takes_precedence_over_path(self):
        # Path has .py extension but content_head says shebang node
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"")
            path = f.name
        try:
            # Extension takes precedence; shebang is only fallback for no extension
            assert detect(path, b"#!/usr/bin/env node\n") == "python"
        finally:
            os.unlink(path)
