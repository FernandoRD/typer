import json
import unittest
from unittest.mock import patch

from autotyper.vault import (BitwardenVault, VaultAlreadyLoggedInError,
                             VaultCallbacks, VaultItem, VaultLoggedInIdentityError,
                             _passkey_count, _passkey_details, is_current_vault_epoch,
                             is_missing_totp_error)


class BitwardenVaultTests(unittest.TestCase):
    def test_login_uses_password_environment_and_keeps_raw_session(self):
        vault = BitwardenVault()
        unlocked = []

        with patch("autotyper.vault._run_bw", return_value="session-token") as run_bw:
            vault._unlock_worker(
                "user@example.test", "master-password",
                VaultCallbacks(on_unlocked=lambda: unlocked.append(True)))

        self.assertEqual(unlocked, [True])
        self.assertEqual(vault._session, "session-token")
        args, kwargs = run_bw.call_args
        self.assertEqual(args[0][0:2], ["login", "user@example.test"])
        self.assertIn("--passwordenv", args[0])
        self.assertIn("BW_PASSWORD", args[0])
        self.assertIn("--nointeraction", args[0])
        self.assertNotIn("--method", args[0])
        self.assertNotIn("--code", args[0])
        self.assertNotIn("master-password", args[0])
        self.assertEqual(kwargs["env_extra"], {"BW_PASSWORD": "master-password"})

    def test_already_logged_in_matching_cli_account_falls_back_without_logout(self):
        vault = BitwardenVault()

        with patch(
            "autotyper.vault._run_bw",
            side_effect=[
                VaultAlreadyLoggedInError("already logged in"),
                json.dumps({"status": "locked", "userEmail": "USER@example.test"}),
                "session-token",
            ],
        ) as run_bw:
            vault._unlock_worker("user@example.test", "master-password", VaultCallbacks())

        self.assertEqual(vault._session, "session-token")
        self.assertEqual(run_bw.call_count, 3)
        self.assertEqual(run_bw.call_args_list[1].args[0], ["status"])
        self.assertEqual(run_bw.call_args_list[2].args[0], [
            "unlock", "--raw", "--nointeraction", "--passwordenv", "BW_PASSWORD",
        ])
        self.assertEqual(run_bw.call_args_list[2].kwargs["env_extra"],
                         {"BW_PASSWORD": "master-password"})

    def test_already_logged_in_different_cli_account_does_not_unlock(self):
        vault = BitwardenVault()
        errors = []

        with patch(
            "autotyper.vault._run_bw",
            side_effect=[
                VaultAlreadyLoggedInError("already logged in"),
                json.dumps({"status": "locked", "userEmail": "other@example.test"}),
            ],
        ) as run_bw:
            vault._unlock_worker(
                "user@example.test", "master-password", VaultCallbacks(on_error=errors.append))

        self.assertIsNone(vault._session)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], VaultLoggedInIdentityError)
        self.assertEqual(run_bw.call_count, 2)

    def test_already_logged_in_invalid_status_does_not_unlock(self):
        vault = BitwardenVault()
        errors = []

        with patch(
            "autotyper.vault._run_bw",
            side_effect=[
                VaultAlreadyLoggedInError("already logged in"),
                json.dumps({"status": "unauthenticated", "userEmail": "user@example.test"}),
            ],
        ) as run_bw:
            vault._unlock_worker(
                "user@example.test", "master-password", VaultCallbacks(on_error=errors.append))

        self.assertIsNone(vault._session)
        self.assertIsInstance(errors[0], VaultLoggedInIdentityError)
        self.assertEqual(run_bw.call_count, 2)

    def test_search_keeps_only_safe_passkey_metadata(self):
        vault = BitwardenVault()
        vault._session = "session"
        found = []
        payload = [{
            "id": "item-1",
            "name": "Example",
            "login": {
                "username": "user@example.test",
                "password": "never copied",
                "totp": "never copied",
                "fido2Credentials": [{"credentialId": "never copied"}],
            },
        }]

        with patch("autotyper.vault._run_bw", return_value=json.dumps(payload)):
            vault._search_worker("Example", VaultCallbacks(on_items=found.append))

        self.assertEqual(found[0][0].id, "item-1")
        self.assertEqual(found[0][0].passkey_count, 1)
        self.assertTrue(found[0][0].has_password)
        self.assertTrue(found[0][0].has_totp)
        self.assertNotIn("never copied", repr(found[0][0]))

    def test_get_totp_calls_cli_only_when_requested(self):
        vault = BitwardenVault()
        vault._session = "session"
        received = []

        with patch("autotyper.vault._run_bw", return_value="123456") as run_bw:
            vault._totp_worker("item-1", VaultCallbacks(on_totp=received.append))

        self.assertEqual(received, ["123456"])
        run_bw.assert_called_once_with(
            ["get", "totp", "item-1"], env_extra={"BW_SESSION": "session"})

    def test_get_totp_is_available_when_list_omits_totp_metadata(self):
        vault = BitwardenVault()
        vault._session = "session"
        found = []
        payload = [{"id": "item-1", "name": "Example", "login": {
            "username": "user@example.test", "password": "never copied"}}]

        with patch("autotyper.vault._run_bw", return_value=json.dumps(payload)):
            vault._search_worker("Example", VaultCallbacks(on_items=found.append))

        self.assertFalse(found[0][0].has_totp)
        received = []
        with patch("autotyper.vault._run_bw", return_value="123456") as run_bw:
            vault._totp_worker(found[0][0].id, VaultCallbacks(on_totp=received.append))

        self.assertEqual(received, ["123456"])
        run_bw.assert_called_once_with(
            ["get", "totp", "item-1"], env_extra={"BW_SESSION": "session"})

    def test_search_includes_totp_only_item(self):
        vault = BitwardenVault()
        vault._session = "session"
        found = []
        payload = [{"id": "totp-only", "name": "Authenticator", "login": {
            "username": "user@example.test", "totp": "never copied"}}]

        with patch("autotyper.vault._run_bw", return_value=json.dumps(payload)):
            vault._search_worker("Authenticator", VaultCallbacks(on_items=found.append))

        self.assertEqual(found[0], [VaultItem(
            "totp-only", "Authenticator", "user@example.test",
            has_password=False, has_totp=True,
        )])

    def test_passkey_normalization_accepts_singleton_and_ignores_invalid_entries(self):
        login = {
            "fido2Credentials": {"credentialId": "fido-id", "rpId": "fido.test"},
            "passkey": [{"credentialId": "passkey-id", "rpId": "passkey.test"}, "invalid"],
        }

        self.assertEqual(_passkey_count(login), 2)
        self.assertEqual(
            [(detail.credential_id, detail.rp_id) for detail in _passkey_details(login)],
            [("fido-id", "fido.test"), ("passkey-id", "passkey.test")],
        )
        self.assertEqual(_passkey_count({"fido2Credentials": ["invalid"]}), 0)
        self.assertEqual(_passkey_details("not a login"), [])

    def test_search_reports_non_list_document_without_attribute_error(self):
        vault = BitwardenVault()
        vault._session = "session"
        errors = []

        with patch("autotyper.vault._run_bw", return_value=json.dumps({"id": "not-a-list"})):
            vault._search_worker("anything", VaultCallbacks(on_error=errors.append))

        self.assertEqual(len(errors), 1)
        self.assertIn("invalid JSON document", str(errors[0]))

    def test_vault_epoch_guard_rejects_password_response_after_lock(self):
        self.assertTrue(is_current_vault_epoch(True, 3, 3))
        self.assertFalse(is_current_vault_epoch(False, 4, 3))
        self.assertFalse(is_current_vault_epoch(True, 4, 3))

    def test_missing_totp_error_classification_is_narrow(self):
        for message in (
            "No TOTP available",
            "No TOTP secret found for this item",
            "TOTP is not configured",
            "Credential does not have a TOTP",
        ):
            self.assertTrue(is_missing_totp_error(RuntimeError(message)))
        self.assertFalse(is_missing_totp_error(RuntimeError("network timeout")))
        self.assertFalse(is_missing_totp_error(RuntimeError("TOTP generation failed")))

    def test_passkey_details_allowlist_excludes_private_material(self):
        vault = BitwardenVault()
        vault._session = "session"
        received = []
        payload = {
            "login": {"fido2Credentials": [{
                "credentialId": "credential-public-id",
                "rpId": "example.test",
                "userHandle": "user-handle",
                "creationDate": "2026-01-01T00:00:00Z",
                "privateKey": "must-not-leak",
                "keyValue": "must-not-leak",
                "seed": "must-not-leak",
            }]},
        }

        with patch("autotyper.vault._run_bw", return_value=json.dumps(payload)) as run_bw:
            vault._passkey_details_worker(
                "item-1", VaultCallbacks(on_passkey_details=received.append))

        self.assertEqual(received[0][0].credential_id, "credential-public-id")
        self.assertEqual(received[0][0].rp_id, "example.test")
        self.assertEqual(received[0][0].user_handle, "user-handle")
        self.assertEqual(received[0][0].metadata, (("Created", "2026-01-01T00:00:00Z"),))
        self.assertNotIn("must-not-leak", repr(received[0][0]))
        run_bw.assert_called_once_with(
            ["get", "item", "item-1"], env_extra={"BW_SESSION": "session"})


if __name__ == "__main__":
    unittest.main()
