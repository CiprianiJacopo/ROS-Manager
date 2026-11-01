import ast
import base64
import hashlib
import io
import os
import threading
import unittest
from unittest import mock

try:
    import paramiko as _real_paramiko
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
except ImportError:  # key tests need paramiko + cryptography
    _real_paramiko = None

DASHBOARD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard.py")

_NAMES = {
    "_cred_set_username", "_make_credential", "_cred_set_to_credential", "_resolve_credential",
    "_cred_usable", "_get_credential_for_site", "_get_device_credential",
    "_ssh_auth_kwargs", "_ssh_connect_cred", "_ssh_connect",
    "_load_private_key", "_key_fingerprint", "_key_public_line", "_apply_ssh_key", "cred_set_add",
    "cred_set_update", "_cred_set_public",
}
_CONSTS = {"CRED_TYPE_PASSWORD", "CRED_TYPE_SSH_KEY", "CRED_TYPES", "MAX_PRIVATE_KEY_BYTES"}


def _load_namespace():
    with open(DASHBOARD, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    ns = {"CRED_TYPE_PASSWORD": "password", "SSH_TIMEOUT": 7}
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in _CONSTS:
            exec(compile(ast.Module([node], []), DASHBOARD, "exec"), ns)
        if isinstance(node, ast.FunctionDef) and node.name in _NAMES:
            exec(compile(ast.Module([node], []), DASHBOARD, "exec"), ns)
    return ns


class CredentialResolutionTests(unittest.TestCase):
    def setUp(self):
        self.ns = _load_namespace()
        self.ns["_decrypt"] = lambda s: s[4:] if s.startswith("enc:") else s
        self.ns["CRED_SETS"] = [
            {"id": "cs_1", "name": "a", "username_enc": "enc:admin", "password_enc": "enc:pw"},
            {"id": "cs_2", "name": "legacy", "username": "old", "password_enc": "enc:pw2"},
        ]
        self.ns["SITES"] = {"s1": {"credential_id": "cs_1"}}
        self.ns["DEVICES"] = {}

    def test_missing_type_is_password(self):
        cred = self.ns["_resolve_credential"]("cs_1")
        self.assertEqual(cred, {"type": "password", "username": "admin", "password": "pw"})

    def test_legacy_plaintext_username(self):
        self.assertEqual(self.ns["_resolve_credential"]("cs_2"),
                         {"type": "password", "username": "old", "password": "pw2"})

    def test_unknown_or_empty_id(self):
        self.assertEqual(self.ns["_resolve_credential"]("nope")["username"], "")
        self.assertEqual(self.ns["_resolve_credential"]("")["username"], "")

    def test_site_credential(self):
        self.assertEqual(self.ns["_get_credential_for_site"]("s1")["username"], "admin")
        self.assertEqual(self.ns["_get_credential_for_site"]("missing")["username"], "")

    def test_device_priority(self):
        d = self.ns["DEVICES"]
        d["1.1.1.1"] = {"credential_id": "cs_2", "ssh_user": "u", "ssh_pass_enc": "enc:p", "site_id": "s1"}
        d["2.2.2.2"] = {"ssh_user": "u", "ssh_pass_enc": "enc:p", "site_id": "s1"}
        d["3.3.3.3"] = {"site_id": "s1"}
        d["4.4.4.4"] = {"credential_id": "gone", "site_id": "s1"}
        g = self.ns["_get_device_credential"]
        get = lambda ip: (g(ip)["username"], g(ip)["password"])
        self.assertEqual(get("1.1.1.1"), ("old", "pw2"))
        self.assertEqual(get("2.2.2.2"), ("u", "p"))
        self.assertEqual(get("3.3.3.3"), ("admin", "pw"))
        self.assertEqual(get("4.4.4.4"), ("admin", "pw"))
        self.assertEqual(get("9.9.9.9"), ("", ""))


class CredUsableTests(unittest.TestCase):
    def test_usable(self):
        u = _load_namespace()["_cred_usable"]
        self.assertTrue(u({"type": "password", "username": "a", "password": "b"}))
        self.assertFalse(u({"type": "password", "username": "a", "password": ""}))
        self.assertTrue(u({"type": "ssh_key", "username": "a", "private_key": "k"}))
        self.assertFalse(u({"type": "ssh_key", "username": "a", "private_key": ""}))
        self.assertFalse(u({"type": "bogus", "username": "a"}))
        self.assertFalse(u(None))


class SshConnectTests(unittest.TestCase):
    def setUp(self):
        self.ns = _load_namespace()
        self.paramiko = mock.MagicMock()
        self.ns["paramiko"] = self.paramiko
        self.client = self.paramiko.SSHClient.return_value

    def test_password_connect_arguments_unchanged(self):
        self.ns["_ssh_connect_cred"]("10.0.0.1", {"type": "password", "username": "admin", "password": "pw"})
        self.client.connect.assert_called_once_with(
            "10.0.0.1", timeout=7, look_for_keys=False, allow_agent=False,
            banner_timeout=9, auth_timeout=9, username="admin", password="pw")

    def test_read_connect_uses_device_credential(self):
        self.ns["_get_device_credential"] = lambda ip: {"type": "password", "username": "u", "password": "p"}
        self.ns["_ssh_connect"]("10.0.0.2")
        kwargs = self.client.connect.call_args.kwargs
        self.assertEqual((kwargs["username"], kwargs["password"]), ("u", "p"))

    def test_unsupported_type_rejected(self):
        with self.assertRaises(ValueError):
            self.ns["_ssh_auth_kwargs"]({"type": "bogus"})


def _ed25519_pem(passphrase=None):
    key = ed25519.Ed25519PrivateKey.generate()
    enc = (serialization.BestAvailableEncryption(passphrase.encode())
           if passphrase else serialization.NoEncryption())
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, enc).decode()


def _rsa_pem(passphrase=None):
    buf = io.StringIO()
    _real_paramiko.RSAKey.generate(2048).write_private_key(buf, password=passphrase)
    return buf.getvalue()


def _ecdsa_pem():
    buf = io.StringIO()
    _real_paramiko.ECDSAKey.generate().write_private_key(buf)
    return buf.getvalue()


@unittest.skipIf(_real_paramiko is None, "paramiko/cryptography not installed")
class SshKeyCredentialTests(unittest.TestCase):
    def setUp(self):
        self.ns = _load_namespace()
        self.ns.update({
            "paramiko": _real_paramiko, "_io": io, "_b64": base64, "hashlib": hashlib,
            "time": __import__("time"), "CRED_SETS": [], "CRED_SETS_LOCK": threading.Lock(),
            "_save_cred_sets": lambda: None,
            "_encrypt": lambda s: "enc:" + s if s else "",
            "_decrypt": lambda s: s[4:] if s.startswith("enc:") else s,
        })

    def test_parse_each_key_type(self):
        load = self.ns["_load_private_key"]
        self.assertEqual(load(_ed25519_pem()).get_name(), "ssh-ed25519")
        self.assertEqual(load(_rsa_pem()).get_name(), "ssh-rsa")
        self.assertTrue(load(_ecdsa_pem()).get_name().startswith("ecdsa-"))

    def test_crlf_and_surrounding_whitespace(self):
        pem = "\n  " + _ed25519_pem().replace("\n", "\r\n") + "  \n"
        self.assertEqual(self.ns["_load_private_key"](pem).get_name(), "ssh-ed25519")

    def test_passphrase_handling(self):
        load = self.ns["_load_private_key"]
        for pem in (_ed25519_pem("s3cret pass"), _rsa_pem("s3cret pass")):
            with self.assertRaisesRegex(ValueError, "passphrase"):
                load(pem)
            with self.assertRaises(ValueError):
                load(pem, "wrong")
            self.assertIsNotNone(load(pem, "s3cret pass"))

    def test_invalid_input_rejected(self):
        load = self.ns["_load_private_key"]
        for bad in ("", "   ", "hello", "-----BEGIN OPENSSH PRIVATE KEY-----\nnope\n-----END OPENSSH PRIVATE KEY-----"):
            with self.assertRaises(ValueError):
                load(bad)
        with self.assertRaisesRegex(ValueError, "too large"):
            load("PRIVATE KEY " + "A" * (16 * 1024))

    def test_fingerprint_and_public_line_match_paramiko(self):
        pem = _ed25519_pem()
        pkey = self.ns["_load_private_key"](pem)
        fp = self.ns["_key_fingerprint"](pkey)
        self.assertRegex(fp, r"^SHA256:[A-Za-z0-9+/]{43}$")
        self.assertEqual(fp, "SHA256:" + base64.b64encode(hashlib.sha256(pkey.asbytes()).digest()).decode().rstrip("="))
        self.assertTrue(self.ns["_key_public_line"](pkey).startswith("ssh-ed25519 "))

    def test_add_key_set_stores_encrypted_and_metadata(self):
        pem = _ed25519_pem("pw")
        cid = self.ns["cred_set_add"]("k", "admin", ctype="ssh_key", private_key=pem, passphrase="pw")
        cs = self.ns["CRED_SETS"][0]
        self.assertEqual(cs["id"], cid)
        self.assertEqual(cs["type"], "ssh_key")
        self.assertTrue(cs["private_key_enc"].startswith("enc:"))
        self.assertNotIn("PRIVATE KEY", {k: v for k, v in cs.items() if k != "private_key_enc"}.__str__())
        self.assertEqual(cs["key_type"], "ssh-ed25519")
        self.assertTrue(cs["fingerprint"].startswith("SHA256:"))
        public = self.ns["_cred_set_public"](cs)
        self.assertNotIn("private_key_enc", public)
        self.assertNotIn("passphrase_enc", public)

    def test_add_invalid_key_stores_nothing(self):
        with self.assertRaises(ValueError):
            self.ns["cred_set_add"]("k", "admin", ctype="ssh_key", private_key="junk")
        with self.assertRaises(ValueError):
            self.ns["cred_set_add"]("k", "admin", "pw", ctype="bogus")
        self.assertEqual(self.ns["CRED_SETS"], [])

    def test_credential_object_and_connect_kwargs(self):
        pem = _rsa_pem("pw")
        self.ns["cred_set_add"]("k", "admin", ctype="ssh_key", private_key=pem, passphrase="pw")
        self.ns["SITES"] = {}
        cred = self.ns["_resolve_credential"](self.ns["CRED_SETS"][0]["id"])
        self.assertEqual(cred["type"], "ssh_key")
        self.assertEqual(cred["username"], "admin")
        kwargs = self.ns["_ssh_auth_kwargs"](cred)
        self.assertEqual(set(kwargs), {"username", "pkey"})
        self.assertEqual(kwargs["pkey"].get_name(), "ssh-rsa")

    def test_update_semantics(self):
        pem1, pem2 = _ed25519_pem("a"), _ed25519_pem()
        self.ns["cred_set_add"]("k", "admin", ctype="ssh_key", private_key=pem1, passphrase="a")
        cs = self.ns["CRED_SETS"][0]
        fp1 = cs["fingerprint"]
        self.ns["cred_set_update"](cs["id"], name="renamed")          # secrets kept
        self.assertEqual((cs["name"], cs["fingerprint"]), ("renamed", fp1))
        self.ns["cred_set_update"](cs["id"], passphrase="a")          # re-validates stored key
        with self.assertRaises(ValueError):
            self.ns["cred_set_update"](cs["id"], passphrase="wrong")
        self.assertEqual(cs["fingerprint"], fp1)                       # failed update leaves set intact
        self.ns["cred_set_update"](cs["id"], private_key=pem2)         # replaced, passphrase cleared
        self.assertNotEqual(cs["fingerprint"], fp1)
        self.assertEqual(cs["passphrase_enc"], "")


if __name__ == "__main__":
    unittest.main()
