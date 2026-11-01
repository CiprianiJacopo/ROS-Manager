import ast
import email.message
import email.parser
import email.policy
import io
import os
import pathlib
import tempfile
import unittest
import urllib.parse


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "dashboard.py"
PARSER_NAMES = {
    "_FormParseError",
    "_UploadedFormFile",
    "_ParsedPostForm",
    "_parse_content_length",
    "_parse_post_form",
    "_save_upload",
}


def load_parser():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    nodes = [
        node for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name in PARSER_NAMES
    ]
    namespace = {
        "_io": io,
        "_tempfile": tempfile,
        "_EmailMessage": email.message.Message,
        "_BytesParser": email.parser.BytesParser,
        "_email_policy": email.policy.default,
        "urllib": urllib,
        "os": os,
        "MAX_UPLOAD_SIZE_BYTES": 10 * 1024 * 1024,
        "UPLOAD_DIR": None,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


PARSER = load_parser()


def parse_body(body, content_type, *, content_length=None):
    length = len(body) if content_length is None else content_length
    headers = {"Content-Type": content_type, "Content-Length": str(length)}
    return PARSER["_parse_post_form"](io.BytesIO(body), headers, length)


class PostFormParserTests(unittest.TestCase):
    def test_dashboard_source_has_no_cgi_import_or_fieldstorage_call(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse(any(alias.name == "cgi" for alias in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, "cgi")
            if isinstance(node, ast.Attribute):
                self.assertNotEqual(node.attr, "FieldStorage")

    def test_urlencoded_values_keep_duplicates_and_blanks(self):
        form = parse_body(
            b"ips=192.0.2.1&tag=&ips=192.0.2.2",
            "application/x-www-form-urlencoded",
        )

        self.assertEqual(form.getvalue("ips"), ["192.0.2.1", "192.0.2.2"])
        self.assertEqual(form.getvalue("tag"), "")
        self.assertEqual(form.getvalue("missing", "default"), "default")

    def test_multipart_fields_and_binary_upload(self):
        boundary = b"upload-boundary"
        body = (
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="ips"\r\n\r\n'
            b"192.0.2.1,192.0.2.2\r\n"
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="file"; filename="router.rsc"\r\n'
            b"Content-Type: application/octet-stream\r\n\r\n"
            b"\x00\xffrouter-data\r\n"
            b"--" + boundary + b"--\r\n"
        )
        form = parse_body(body, "multipart/form-data; boundary=upload-boundary")

        self.assertEqual(form.getvalue("ips"), "192.0.2.1,192.0.2.2")
        upload = form["file"]
        self.assertEqual(upload.filename, "router.rsc")
        self.assertEqual(upload.file.read(), b"\x00\xffrouter-data")

    def test_rejects_missing_content_length(self):
        headers = {"Content-Type": "multipart/form-data; boundary=abc"}
        with self.assertRaises(PARSER["_FormParseError"]) as raised:
            PARSER["_parse_post_form"](io.BytesIO(b""), headers, 0)
        self.assertEqual(raised.exception.status, 411)

    def test_rejects_invalid_content_length_headers(self):
        for value in ("", "-1", "1.5", "1, 1", "１２"):
            with self.subTest(value=value):
                with self.assertRaises(PARSER["_FormParseError"]):
                    PARSER["_parse_content_length"]({"Content-Length": value})
        self.assertEqual(
            PARSER["_parse_content_length"]({"Content-Length": "10485760"}),
            10 * 1024 * 1024,
        )

    def test_rejects_oversized_request_before_reading(self):
        class Unreadable:
            def read(self, _length):
                raise AssertionError("oversized body must not be read")

        with self.assertRaises(PARSER["_FormParseError"]) as raised:
            PARSER["_parse_post_form"](
                Unreadable(),
                {"Content-Length": "10485761"},
                10 * 1024 * 1024 + 1,
            )
        self.assertEqual(raised.exception.status, 413)

    def test_rejects_short_body_and_unsupported_content_type(self):
        with self.assertRaisesRegex(PARSER["_FormParseError"], "incompleto"):
            PARSER["_parse_post_form"](
                io.BytesIO(b"short"),
                {"Content-Length": "10", "Content-Type": "application/x-www-form-urlencoded"},
                10,
            )
        with self.assertRaises(PARSER["_FormParseError"]) as raised:
            parse_body(b"body", "application/json")
        self.assertEqual(raised.exception.status, 415)

    def test_rejects_malformed_multipart(self):
        incomplete = (
            b"--abc\r\n"
            b'Content-Disposition: form-data; name="field"\r\n\r\n'
            b"value\r\n"
        )
        with self.assertRaises(PARSER["_FormParseError"]):
            parse_body(incomplete, "multipart/form-data; boundary=abc")

    def test_upload_is_written_atomically_and_temp_file_is_removed(self):
        with tempfile.TemporaryDirectory() as upload_dir:
            previous_upload_dir = PARSER["UPLOAD_DIR"]
            PARSER["UPLOAD_DIR"] = upload_dir
            try:
                item = PARSER["_UploadedFormFile"](
                    "../../router.rsc", b"\x00\xff" + b"x" * 150_000)
                filename, path = PARSER["_save_upload"](item)

                self.assertEqual(filename, "router.rsc")
                self.assertEqual(
                    pathlib.Path(path).read_bytes(), b"\x00\xff" + b"x" * 150_000)
                self.assertEqual(os.listdir(upload_dir), ["router.rsc"])
            finally:
                PARSER["UPLOAD_DIR"] = previous_upload_dir

    def test_upload_temp_file_is_removed_if_copy_fails(self):
        class BrokenReader:
            def read(self, _size):
                raise OSError("read failed")

        with tempfile.TemporaryDirectory() as upload_dir:
            previous_upload_dir = PARSER["UPLOAD_DIR"]
            PARSER["UPLOAD_DIR"] = upload_dir
            try:
                item = PARSER["_UploadedFormFile"]("router.rsc", b"")
                item.file = BrokenReader()

                with self.assertRaisesRegex(OSError, "read failed"):
                    PARSER["_save_upload"](item)

                self.assertEqual(os.listdir(upload_dir), [])
            finally:
                PARSER["UPLOAD_DIR"] = previous_upload_dir


if __name__ == "__main__":
    unittest.main()
