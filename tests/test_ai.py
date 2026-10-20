import json
import os
import signal
import sys
import threading
import time
import unittest
from unittest.mock import Mock, call, patch

from autotyper.ai import (
    AICallbacks,
    AICancelledError,
    AIGenerator,
    AIOutputError,
    AITimeoutError,
    AIUnavailableError,
    Provider,
    ProviderStatus,
    _ProcessResult,
    _generation_argv,
    _parse_result,
    _run_cli,
    _safe_env,
    _sanitize_stderr,
    _terminate_process,
    models_for,
    provider_status,
)


class AISecurityTests(unittest.TestCase):
    def test_claude_prompt_is_stdin_only_and_result_is_delivered_once(self):
        generator = AIGenerator()
        done = threading.Event()
        received = []
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = list(argv)
            captured["stdin"] = kwargs["stdin"]
            return _ProcessResult(
                json.dumps({
                    "type": "result", "subtype": "success", "is_error": False,
                    "result": "validated final text",
                }).encode(),
                b"",
            )

        ready = ProviderStatus(
            Provider.CLAUDE, "claude", True, True, True, True, "ready")
        callbacks = AICallbacks(
            on_text=lambda text: received.append(("text", text)),
            on_done=lambda text: (received.append(("done", text)), done.set()),
            on_error=lambda error: (received.append(("error", error)), done.set()),
        )
        with patch("autotyper.ai.provider_status", return_value=ready), \
                patch("autotyper.ai.shutil.which", return_value="/usr/bin/claude"), \
                patch("autotyper.ai._run_cli", side_effect=fake_run):
            generator.generate(
                "SECRET USER PROMPT", "en", "default", callbacks,
                provider=Provider.CLAUDE,
            )
            self.assertTrue(done.wait(2))

        self.assertNotIn("SECRET USER PROMPT", captured["argv"])
        self.assertIn(b"SECRET USER PROMPT", captured["stdin"])
        self.assertEqual(received, [
            ("text", "validated final text"),
            ("done", "validated final text"),
        ])
        self.assertIn("--restricted", captured["argv"])
        self.assertIn("--no-session-persistence", captured["argv"])
        self.assertIn("--permission-prompts", captured["argv"])

    def test_codex_is_explicitly_fail_closed_without_probing_or_models(self):
        with patch("autotyper.ai.shutil.which", return_value="/usr/bin/codex"), \
                patch("autotyper.ai._run_cli") as run_cli:
            status = provider_status(Provider.CODEX)

        self.assertTrue(status.installed)
        self.assertFalse(status.safe)
        self.assertFalse(status.available)
        self.assertIn("disabled", status.message.lower())
        self.assertEqual(models_for(Provider.CODEX, status), [])
        run_cli.assert_not_called()
        with self.assertRaises(AIUnavailableError):
            _generation_argv(Provider.CODEX, "/usr/bin/codex", "default", None)
        with self.assertRaises(AIUnavailableError):
            AIGenerator().generate(
                "prompt", "en", "default", AICallbacks(), provider=Provider.CODEX)

    def test_models_require_matching_safe_available_status(self):
        ready = ProviderStatus(
            Provider.CLAUDE, "claude", True, True, True, True, "ready")
        unavailable = ProviderStatus(
            Provider.CLAUDE, "claude", True, True, False, False, "disabled")
        wrong_provider = ProviderStatus(
            Provider.CODEX, "codex", True, False, False, False, "disabled")

        self.assertEqual([model.id for model in models_for(Provider.CLAUDE, ready)],
                         ["default"])
        self.assertEqual(models_for(Provider.CLAUDE, unavailable), [])
        self.assertEqual(models_for(Provider.CLAUDE, wrong_provider), [])

    def test_environment_is_allowlisted_and_omits_secret_sources(self):
        source = {
            "PATH": "/usr/bin", "HOME": "/home/test", "LANG": "C.UTF-8",
            "ANTHROPIC_API_KEY": "secret", "OPENAI_API_KEY": "secret",
            "BW_SESSION": "secret", "SSH_AUTH_SOCK": "/tmp/agent",
            "AWS_SECRET_ACCESS_KEY": "secret", "HTTP_PROXY": "secret-proxy",
        }
        with patch.dict(os.environ, source, clear=True):
            env = _safe_env()
        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertEqual(env["HOME"], "/home/test")
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("BW_SESSION", env)
        self.assertNotIn("SSH_AUTH_SOCK", env)
        self.assertNotIn("HTTP_PROXY", env)

    def test_incomplete_or_error_output_is_discarded(self):
        with self.assertRaises(AIOutputError):
            _parse_result(Provider.CLAUDE, b'{"type":"result","is_error":true,"result":"partial"}')
        with self.assertRaises(AIOutputError):
            _parse_result(Provider.CLAUDE, b'{"type":"result","result":')

    def test_claude_result_requires_explicit_success_fields(self):
        invalid_fields = (
            {},
            {"is_error": None, "subtype": "success"},
            {"is_error": 0, "subtype": "success"},
            {"is_error": "false", "subtype": "success"},
            {"is_error": False},
            {"is_error": False, "subtype": None},
            {"is_error": False, "subtype": "error"},
        )
        for fields in invalid_fields:
            with self.subTest(fields=fields), self.assertRaises(AIOutputError):
                payload = {"type": "result", "result": "must reject", **fields}
                _parse_result(Provider.CLAUDE, json.dumps(payload).encode())

        accepted = {
            "type": "result", "is_error": False, "subtype": "success",
            "result": "accepted",
        }
        self.assertEqual(
            _parse_result(Provider.CLAUDE, json.dumps(accepted).encode()), "accepted")

    def test_timeout_discards_output(self):
        with self.assertRaises(AITimeoutError):
            _run_cli(
                [sys.executable, "-c", "import time; print('partial', flush=True); time.sleep(5)"],
                stdin=b"", timeout=0.1,
            )

    def test_cancel_terminates_process_and_discards_output(self):
        cancel = threading.Event()
        errors = []

        def worker():
            try:
                _run_cli(
                    [sys.executable, "-c",
                     "import time; print('partial', flush=True); time.sleep(5)"],
                    stdin=b"", timeout=3, cancel_event=cancel,
                )
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        time.sleep(0.1)
        cancel.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], AICancelledError)

    def test_generator_cancel_reports_cancelled_and_no_result(self):
        generator = AIGenerator(timeout=3)
        finished = threading.Event()
        results = []
        errors = []
        ready = ProviderStatus(
            Provider.CLAUDE, "claude", True, True, True, True, "ready")
        command = [
            sys.executable, "-c",
            "import time; print('partial', flush=True); time.sleep(5)",
        ]
        callbacks = AICallbacks(
            on_text=results.append,
            on_done=results.append,
            on_error=lambda exc: (errors.append(exc), finished.set()),
        )
        with patch("autotyper.ai.provider_status", return_value=ready), \
                patch("autotyper.ai.shutil.which", return_value=sys.executable), \
                patch("autotyper.ai._generation_argv", return_value=command):
            generator.generate(
                "prompt", "en", "default", callbacks, provider=Provider.CLAUDE)
            time.sleep(0.1)
            self.assertTrue(generator.cancel())
            self.assertTrue(finished.wait(2))

        self.assertEqual(results, [])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], AICancelledError)

    def test_cancel_winning_before_publication_never_emits_result(self):
        generator = AIGenerator(timeout=3)
        result_ready = threading.Event()
        release_result = threading.Event()
        finished = threading.Event()
        published = []
        errors = []
        ready = ProviderStatus(
            Provider.CLAUDE, "claude", True, True, True, True, "ready")

        def fake_run(*_args, **_kwargs):
            result_ready.set()
            self.assertTrue(release_result.wait(2))
            return _ProcessResult(json.dumps({
                "type": "result", "subtype": "success", "is_error": False,
                "result": "must not publish",
            }).encode(), b"")

        callbacks = AICallbacks(
            on_text=published.append,
            on_done=published.append,
            on_error=lambda exc: (errors.append(exc), finished.set()),
        )
        with patch("autotyper.ai.provider_status", return_value=ready), \
                patch("autotyper.ai.shutil.which", return_value="/usr/bin/claude"), \
                patch("autotyper.ai._run_cli", side_effect=fake_run):
            generator.generate(
                "prompt", "en", "default", callbacks, provider=Provider.CLAUDE)
            self.assertTrue(result_ready.wait(2))
            self.assertTrue(generator.cancel())
            release_result.set()
            self.assertTrue(finished.wait(2))

        self.assertEqual(published, [])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], AICancelledError)

    def test_windows_is_fail_closed_before_starting_any_process(self):
        with patch("autotyper.ai.os.name", "nt"), \
                patch("autotyper.ai.shutil.which", return_value=r"C:\\bin\\claude.exe"), \
                patch("autotyper.ai.subprocess.Popen") as popen:
            status = provider_status(Provider.CLAUDE)
            with self.assertRaises(AIUnavailableError):
                AIGenerator().generate(
                    "prompt", "en", "default", AICallbacks(),
                    provider=Provider.CLAUDE,
                )

        self.assertFalse(status.safe)
        self.assertFalse(status.available)
        popen.assert_not_called()

    def test_posix_termination_always_sigkills_group_after_leader_exit(self):
        process = Mock(pid=4321)
        process.wait.return_value = 0
        with patch("autotyper.ai.os.name", "posix"), \
                patch("autotyper.ai.os.killpg") as killpg, \
                patch("autotyper.ai.time.sleep") as sleep:
            _terminate_process(process)

        self.assertEqual(killpg.call_args_list, [
            call(4321, signal.SIGTERM),
            call(4321, signal.SIGKILL),
        ])
        sleep.assert_called_once_with(0.5)
        process.wait.assert_called_once_with(timeout=0.5)

    def test_posix_termination_tolerates_missing_process_group(self):
        process = Mock(pid=4321)
        process.wait.return_value = 0
        with patch("autotyper.ai.os.name", "posix"), \
                patch("autotyper.ai.os.killpg", side_effect=ProcessLookupError) as killpg:
            _terminate_process(process)

        self.assertEqual(killpg.call_count, 2)

    def test_subprocess_runs_in_clean_temporary_directory(self):
        result = _run_cli(
            [sys.executable, "-c", "import os; print(os.getcwd())"],
            stdin=b"", timeout=2,
        )
        cwd = result.stdout.decode().strip()
        self.assertIn("autotyper-ai-", cwd)
        self.assertFalse(os.path.exists(cwd))

    def test_stderr_sanitization_redacts_tokens_and_key_values(self):
        raw = (
            b"Authorization: Bearer-secret-value\n"
            b"api_key=sk-ant-abcdefghijklmnopqrstuvwxyz\n"
            b"password=hunter2\n"
        )
        cleaned = _sanitize_stderr(raw)
        self.assertNotIn("Bearer-secret-value", cleaned)
        self.assertNotIn("sk-ant-abcdefghijklmnopqrstuvwxyz", cleaned)
        self.assertNotIn("hunter2", cleaned)
        self.assertIn("[REDACTED]", cleaned)

    def test_failed_process_never_surfaces_stderr(self):
        secret = "unstructured-private-value"
        with self.assertRaisesRegex(Exception, "local provider failed") as caught:
            _run_cli(
                [sys.executable, "-c", f"import sys; sys.stderr.write('{secret}'); sys.exit(7)"],
                stdin=b"", timeout=2,
            )
        self.assertNotIn(secret, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
