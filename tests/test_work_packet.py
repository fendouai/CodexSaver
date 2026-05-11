from __future__ import annotations

import sys
from pathlib import Path

from codexsaver.schema import WorkPacketInput
from codexsaver.work_packet import (
    WorkPacketRuntime,
    changed_files_from_patch,
    search_code,
    normalize_patch,
    verify_patch_policy,
)


class FakeProvider:
    def __init__(self, actions):
        self.actions = list(actions)

    def complete_json(self, system_prompt, payload):
        assert "bounded" in system_prompt
        return self.actions.pop(0)


class UnexpectedProvider:
    def complete_json(self, system_prompt, payload):
        raise AssertionError("provider should not be called")


def test_work_packet_runtime_returns_success_when_preflight_already_satisfied(tmp_path):
    target = tmp_path / "hello.py"
    target.write_text("def greet():\n    return 'hello'\n", encoding="utf-8")
    runtime = WorkPacketRuntime(UnexpectedProvider())

    result = runtime.run(WorkPacketInput(
        goal="Ensure greet returns hello",
        files=["hello.py"],
        constraints=[],
        acceptance_criteria=["greet returns hello"],
        allowed_files=["hello.py"],
        forbidden_paths=[],
        allowed_commands=[f'"{sys.executable}" -c "import hello; assert hello.greet() == \'hello\'"'],
        workspace=str(tmp_path),
        max_iterations=2,
    ))

    assert result["status"] == "success"
    assert result["summary"] == "Work packet already satisfied before delegation."
    assert result["changed_files"] == []
    assert result["patch"] == ""
    assert result["checks"][0]["exit_code"] == 0


def test_work_packet_runtime_patch_check_finish(tmp_path):
    target = tmp_path / "hello.py"
    target.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")
    patch = """diff --git a/hello.py b/hello.py
--- a/hello.py
+++ b/hello.py
@@ -1,2 +1,2 @@
 def greet():
-    return 'hi'
+    return 'hello'
"""
    runtime = WorkPacketRuntime(FakeProvider([
        {
            "status": "success",
            "summary": "Updated greeting.",
            "patch": patch,
            "changed_files": ["hello.py"],
            "risk_notes": [],
        },
    ]))
    result = runtime.run(WorkPacketInput(
        goal="Update greeting",
        files=["hello.py"],
        constraints=[],
        acceptance_criteria=["greet returns hello"],
        allowed_files=["hello.py"],
        forbidden_paths=[],
        allowed_commands=[f'"{sys.executable}" -c "import hello; assert hello.greet() == \'hello\'"'],
        workspace=str(tmp_path),
        max_iterations=4,
    ))
    assert result["status"] == "success"
    assert result["route"] == "deepseek"
    assert result["changed_files"] == ["hello.py"]
    assert result["checks"][0]["exit_code"] == 0
    assert target.read_text(encoding="utf-8") == "def greet():\n    return 'hi'\n"


def test_work_packet_runtime_repairs_after_failed_patch(tmp_path):
    target = tmp_path / "hello.py"
    target.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")
    bad_patch = """diff --git a/hello.py b/hello.py
--- a/hello.py
+++ b/hello.py
@@ -9,2 +9,2 @@
-missing
+broken
"""
    good_patch = """diff --git a/hello.py b/hello.py
--- a/hello.py
+++ b/hello.py
@@ -1,2 +1,2 @@
 def greet():
-    return 'hi'
+    return 'hello'
"""
    runtime = WorkPacketRuntime(FakeProvider([
        {
            "status": "success",
            "summary": "bad",
            "patch": bad_patch,
            "changed_files": ["hello.py"],
            "risk_notes": [],
        },
        {
            "status": "success",
            "summary": "good",
            "patch": good_patch,
            "changed_files": ["hello.py"],
            "risk_notes": [],
        },
    ]))
    result = runtime.run(WorkPacketInput(
        goal="Update greeting",
        files=["hello.py"],
        constraints=[],
        acceptance_criteria=["greet returns hello"],
        allowed_files=["hello.py"],
        forbidden_paths=[],
        allowed_commands=[f'"{sys.executable}" -c "import hello; assert hello.greet() == \'hello\'"'],
        workspace=str(tmp_path),
        max_iterations=2,
    ))
    assert result["status"] == "success"
    assert result["metrics"]["iterations"] == 2


def test_verify_patch_policy_rejects_outside_allowed_file():
    patch = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-a
+b
"""
    packet = WorkPacketInput(
        goal="change",
        files=[],
        constraints=[],
        acceptance_criteria=[],
        allowed_files=["b.py"],
        forbidden_paths=[],
        allowed_commands=[],
    )
    result = verify_patch_policy(patch, packet)
    assert result.ok is False
    assert "outside allowed_files" in result.reason


def test_changed_files_from_patch():
    patch = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-a
+b
"""
    assert changed_files_from_patch(patch) == ["a.py"]


def test_search_code_reports_invalid_regex(tmp_path):
    result = search_code(Path(tmp_path), "[")
    assert result["type"] == "search_error"


def test_normalize_patch_adds_trailing_newline():
    assert normalize_patch("diff") == "diff\n"
