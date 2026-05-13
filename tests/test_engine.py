from __future__ import annotations

import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from codexsaver.engine import CodexSaverEngine, DEFAULT_CONSTRAINTS


class TestCodexSaverEngine:
    def setup_method(self):
        self.engine = CodexSaverEngine()

    def test_delegate_task_routes_high_risk_to_codex(self):
        result = self.engine.delegate_task({
            "instruction": "fix security vulnerability",
            "files": ["src/auth/login.go"],
        })
        assert result["route"] == "codex"
        assert result["status"] == "needs_codex"
        assert result["estimated_savings_percent"] == 0
        assert result["interaction"]["mode"] == "codex_takeover"
        assert "route=codex" in result["interaction"]["route_label"]

    def test_delegate_task_routes_unknown_to_codex(self):
        result = self.engine.delegate_task({
            "instruction": "make it production ready",
            "files": ["src/app.py"],
        })
        assert result["route"] == "codex"
        assert result["status"] == "needs_codex"

    def test_delegate_task_dry_run_returns_preview(self):
        result = self.engine.delegate_task({
            "instruction": "add unit tests for utils",
            "files": [],
            "dry_run": True,
        })
        assert result["status"] == "dry_run"
        assert result["route"] == "deepseek"
        assert "task_preview" in result
        assert "decision" in result
        assert result["interaction"]["mode"] == "preview"
        assert "No external model call" in result["interaction"]["detail"]

    def test_delegate_task_calls_deepseek(self):
        with patch("codexsaver.engine.ProviderClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.complete_task.return_value = {
                "status": "success",
                "summary": "added tests",
                "changed_files": ["tests/foo_test.py"],
                "patch": "diff",
                "commands_to_run": [f'"{sys.executable}" -c "print(\'ok\')"'],
                "risk_notes": [],
            }
            MockClient.return_value = mock_instance

            result = self.engine.delegate_task({
                "instruction": "add unit tests for utils",
                "files": [],
            })

            assert result["route"] == "deepseek"
            assert result["status"] == "success"
            assert result["provider"]["name"] == "deepseek"
            assert result["estimated_savings_percent"] > 0
            assert result["interaction"]["mode"] == "delegated_execution"
            assert "configured worker provider" in result["interaction"]["headline"]
            assert "compression" in result
            mock_instance.complete_task.assert_called_once()

    def test_delegate_task_deepseek_failure_returns_codex(self):
        with patch("codexsaver.engine.ProviderClient") as MockClient:
            from codexsaver.provider import ProviderError
            mock_instance = MagicMock()
            mock_instance.complete_task.side_effect = ProviderError("API error")
            MockClient.return_value = mock_instance

            result = self.engine.delegate_task({
                "instruction": "add unit tests for utils",
                "files": [],
            })

            assert result["route"] == "codex"
            assert result["status"] == "failed"
            assert result["interaction"]["mode"] == "codex_takeover"

    def test_delegate_task_verification_failure(self):
        with patch("codexsaver.engine.ProviderClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.complete_task.return_value = {
                "status": "success",
                "summary": "changed auth",
                "changed_files": ["src/auth/login.go"],
                "patch": "diff",
                "commands_to_run": [],
                "risk_notes": [],
            }
            MockClient.return_value = mock_instance

            result = self.engine.delegate_task({
                "instruction": "refactor auth service",
                "files": ["src/auth/login.go"],
            })

            assert result["status"] == "needs_codex"

    def test_default_constraints_added(self):
        with patch("codexsaver.engine.ProviderClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.complete_task.return_value = {
                "status": "success",
                "summary": "done",
                "changed_files": [],
                "patch": "",
                "commands_to_run": [],
                "risk_notes": [],
            }
            MockClient.return_value = mock_instance

            result = self.engine.delegate_task({
                "instruction": "explain the code",
                "files": [],
                "constraints": ["be concise"],
            })

            mock_instance.complete_task.assert_called_once()
            task = mock_instance.complete_task.call_args[0][0]
            assert "be concise" in task.constraints
            for c in DEFAULT_CONSTRAINTS:
                assert c in task.constraints

    def test_max_files_parameter(self):
        with patch("codexsaver.engine.ProviderClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.complete_task.return_value = {
                "status": "success",
                "summary": "done",
                "changed_files": [],
                "patch": "",
                "commands_to_run": [],
                "risk_notes": [],
            }
            MockClient.return_value = mock_instance

            self.engine.delegate_task({
                "instruction": "add tests",
                "files": [],
                "max_files": 3,
            })

            task = mock_instance.complete_task.call_args[0][0]
            assert task.files == []

    def test_workspace_is_forwarded_to_worker_and_verifier(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sample = os.path.join(tmpdir, "sample.txt")
            with open(sample, "w") as f:
                f.write("hello")
            with patch("codexsaver.engine.ProviderClient") as MockClient:
                mock_instance = MagicMock()
                mock_instance.complete_task.return_value = {
                    "status": "success",
                    "summary": "done",
                    "changed_files": [],
                    "patch": "",
                    "commands_to_run": [],
                    "risk_notes": [],
                }
                MockClient.return_value = mock_instance

                result = self.engine.delegate_task({
                    "instruction": "explain this file",
                    "files": ["sample.txt"],
                    "workspace": tmpdir,
                })

                task = mock_instance.complete_task.call_args[0][0]
                assert task.workspace == os.path.realpath(tmpdir)
                assert task.files[0].path == os.path.realpath(sample)
                assert result["verification"]["executed_commands"] == []

    def test_delegate_task_runs_verification_commands(self):
        with patch("codexsaver.engine.ProviderClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.complete_task.return_value = {
                "status": "success",
                "summary": "added tests",
                "changed_files": ["tests/foo_test.py"],
                "patch": "diff",
                "commands_to_run": ['python -c "print(123)"'],
                "risk_notes": [],
            }
            MockClient.return_value = mock_instance

            result = self.engine.delegate_task({
                "instruction": "add unit tests for utils",
                "files": [],
            })

            assert result["status"] == "success"
            assert result["verification"]["executed_commands"][0]["exit_code"] == 0

    def test_delegate_work_packet_dry_run(self):
        result = self.engine.delegate_work_packet({
            "goal": "add unit tests for utils",
            "files": ["tests/test_utils.py"],
            "allowed_files": ["tests/test_utils.py"],
            "dry_run": True,
        })
        assert result["status"] == "dry_run"
        assert result["route"] == "deepseek"
        assert result["work_packet_preview"]["allowed_files"] == ["tests/test_utils.py"]

    def test_delegate_work_packet_routes_high_risk_to_codex(self):
        result = self.engine.delegate_work_packet({
            "goal": "fix security vulnerability",
            "files": ["src/auth/login.go"],
        })
        assert result["route"] == "codex"
        assert result["status"] == "needs_codex"

    def test_delegate_work_packet_requires_allowed_files_for_writes(self):
        result = self.engine.delegate_work_packet({
            "goal": "add unit tests for utils",
            "files": [],
        })
        assert result["route"] == "codex"
        assert result["status"] == "needs_codex"
        assert "allowed_files" in result["message"]

    def test_delegate_task_includes_compression_info_when_enabled(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            '{"compression": {"enabled": true, "level": "lite"}}',
            encoding="utf-8",
        )
        monkeypatch.setattr("codexsaver.config.CONFIG_PATH", config_path)
        with patch("codexsaver.engine.ProviderClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.complete_task.return_value = {
                "status": "success",
                "summary": "done",
                "changed_files": [],
                "patch": "",
                "commands_to_run": [],
                "risk_notes": [],
            }
            MockClient.return_value = mock_instance

            result = self.engine.delegate_task({
                "instruction": "add tests",
                "files": [],
            })

            assert result["compression"] == {"enabled": True, "level": "lite"}
            assert result["interaction"]["compression"]["enabled"] is True
