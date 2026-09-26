"""Tests for the file scorer (T-3.3)."""
from __future__ import annotations

import pytest

from skillissue.pipeline.sample.scorer import (
    FileScore,
    _RISK_HIGH,
    _RISK_MED,
    _TEST_FILE_PATTERNS,
    _TEST_DIRS,
    _ENTRYPOINT_NAMES,
    _GENERATED_PATTERNS,
    is_entrypoint,
    is_generated,
    is_test,
    risk_path_score,
    score_file,
    score_files,
)


# =====================================================================
# Risk path scoring
# =====================================================================


class TestRiskPathScore:
    def test_auth_high_risk(self):
        assert risk_path_score("auth/login.py") == 1.0

    def test_payment_high_risk(self):
        assert risk_path_score("services/payment.py") == 1.0

    def test_sql_high_risk(self):
        assert risk_path_score("db/queries.py") == 1.0

    def test_secret_high_risk(self):
        assert risk_path_score("crypto/keys.py") == 1.0

    def test_api_medium_risk(self):
        assert risk_path_score("api/routes.py") == 0.5

    def test_router_medium_risk(self):
        assert risk_path_score("web/router.py") == 0.5

    def test_handler_high_risk(self):
        # "handler" is in the high-risk regex
        assert risk_path_score("handlers/auth.py") >= 0.5

    def test_low_risk_path(self):
        assert risk_path_score("utils/helpers.py") == 0.0

    def test_zero_risk_path(self):
        assert risk_path_score("models/user.py") == 0.0

    def test_case_insensitive(self):
        assert risk_path_score("AUTH/login.py") == 1.0

    def test_high_risk_with_extension(self):
        # Path component before .py should still match
        assert risk_path_score("services/payment.py") == 1.0

    def test_payment_dir(self):
        assert risk_path_score("payment/processor.py") == 1.0

    def test_billing_dir(self):
        assert risk_path_score("billing/invoice.py") == 1.0

    def test_admin_dir(self):
        assert risk_path_score("admin/panel.py") == 1.0

    def test_empty_string(self):
        assert risk_path_score("") == 0.0


# =====================================================================
# Entrypoint detection
# =====================================================================


class TestIsEntrypoint:
    def test_main_py(self):
        assert is_entrypoint("main.py")

    def test_app_py(self):
        assert is_entrypoint("app.py")

    def test_manage_py(self):
        assert is_entrypoint("manage.py")

    def test_server_js(self):
        assert is_entrypoint("server.js")

    def test_index_ts(self):
        assert is_entrypoint("index.ts")

    def test_main_go(self):
        assert is_entrypoint("main.go")

    def test_not_entrypoint(self):
        assert not is_entrypoint("utils/helpers.py")

    def test_regular_module(self):
        assert not is_entrypoint("auth/login.py")


# =====================================================================
# Test detection
# =====================================================================


class TestIsTest:
    def test_test_prefix_py(self):
        assert is_test("tests/test_auth.py")

    def test_test_suffix_py(self):
        assert is_test("auth/test_login.py")

    def test_test_dir(self):
        assert is_test("tests/conftest.py")

    def test_spec_dir(self):
        assert is_test("spec/unit.spec.js")

    def test_e2e_dir(self):
        assert is_test("e2e/login.spec.ts")

    def test_not_test(self):
        assert not is_test("src/auth/login.py")

    def test_fixtures_dir(self):
        # fixtures is a test-related directory
        assert is_test("tests/fixtures/data.json")


# =====================================================================
# Generated detection
# =====================================================================


class TestIsGenerated:
    def test_minified_js(self):
        assert is_generated("app.min.js")

    def test_minified_css(self):
        assert is_generated("styles.min.css")

    def test_generated_in_filename(self):
        # is_generated checks filename only — "generated" must be in the filename
        assert is_generated("001_generated.py")

    def test_code_generated_in_filename(self):
        # "Code generated" pattern with space (case-insensitive)
        assert is_generated("config_Code generated.py")

    def test_do_not_edit_marker(self):
        # "DO NOT EDIT" pattern in filename
        assert is_generated("config_DO NOT EDIT.py")

    def test_not_generated(self):
        assert not is_generated("auth/login.py")

    def test_regular_file(self):
        assert not is_generated("utils/helpers.py")


# =====================================================================
# FileScore construction and scoring
# =====================================================================


class TestScoreFile:
    def _score(self, path, lines=200):
        return score_file(path, {path: lines})

    def test_returns_file_score(self):
        result = self._score("auth/login.py")
        assert isinstance(result, FileScore)

    def test_high_risk_gets_higher_score(self):
        high = self._score("auth/login.py")
        low = self._score("utils/helpers.py")
        assert high.final_score > low.final_score

    def test_entrypoint_boost(self):
        ep = self._score("main.py")
        assert ep.is_entrypoint
        # entrypoints get a boost
        normal = self._score("utils/helpers.py", lines=50)
        assert ep.final_score >= normal.final_score

    def test_has_selection_reason(self):
        result = self._score("auth/login.py")
        assert result.selection_reason != ""

    def test_score_clamped_to_one(self):
        result = self._score("auth/payment/crypto/login.py", lines=10_000)
        assert result.final_score <= 1.0

    def test_score_non_negative(self):
        result = self._score("utils/helpers.py", lines=10)
        assert result.final_score >= 0.0


# =====================================================================
# Batch scoring
# =====================================================================


class TestScoreFiles:
    def test_returns_list(self):
        result = score_files(["a.py", "b.py"], {"a.py": 100, "b.py": 50})
        assert isinstance(result, list)

    def test_sorted_by_score_descending(self):
        result = score_files(["a.py", "b.py"], {"a.py": 100, "b.py": 50})
        scores = [fs.final_score for fs in result]
        assert scores == sorted(scores, reverse=True)

    def test_test_files_penalized(self):
        result = score_files(
            ["tests/test_a.py", "src/auth.py"],
            {"tests/test_a.py": 100, "src/auth.py": 100},
        )
        for fs in result:
            if fs.path == "tests/test_a.py":
                assert fs.is_test

    def test_missing_file_in_dict(self):
        # When file_lines is empty, file gets default line count (0)
        result = score_files(["a.py"], {})
        # Returns a FileScore with default values
        assert len(result) == 1
        assert result[0].path == "a.py"

    def test_signal_paths_boost(self):
        result = score_files(
            ["auth/login.py"],
            {"auth/login.py": 200},
            signal_paths=["auth/login.py"],
        )
        for fs in result:
            if fs.path == "auth/login.py":
                assert fs.final_score > 0

    def test_relative_paths_accepted(self):
        result = score_files(["src/auth/login.py"], {"src/auth/login.py": 100})
        assert len(result) == 1
        assert result[0].path == "src/auth/login.py"
