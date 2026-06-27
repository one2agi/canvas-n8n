import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import automation_cli


class AutomationCliTests(unittest.TestCase):
    def test_collects_image_urls_from_repeated_args_and_file(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write("https://example.com/file-a.png\n\nhttps://example.com/file-b.png\n")
            path = f.name
        try:
            args = automation_cli.parse_args([
                "run",
                "--workflow", "ecommerce-main",
                "--image-url", "https://example.com/arg.png",
                "--image-list", path,
            ])

            self.assertEqual(automation_cli.collect_image_urls(args), [
                "https://example.com/arg.png",
                "https://example.com/file-a.png",
                "https://example.com/file-b.png",
            ])
        finally:
            os.remove(path)

    def test_run_no_wait_posts_workflow_name_and_prints_task_id(self):
        calls = []

        def fake_json_request(method, url, payload=None):
            calls.append((method, url, payload))
            return {"task_id": "auto_123", "status": "queued"}

        out = StringIO()
        args = automation_cli.parse_args([
            "run",
            "--server", "http://127.0.0.1:3000",
            "--workflow", "ecommerce-main",
            "--image-url", "https://example.com/product.png",
            "--callback-url", "http://127.0.0.1:3000/api/automation/test-callback",
            "--no-wait",
        ])

        with patch.object(automation_cli, "json_request", side_effect=fake_json_request):
            exit_code = automation_cli.run_command(args, stdout=out)

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, [(
            "POST",
            "http://127.0.0.1:3000/api/automation/workflow-runs",
            {
                "workflow_name": "ecommerce-main",
                "image_urls": ["https://example.com/product.png"],
                "callback_url": "http://127.0.0.1:3000/api/automation/test-callback",
            },
        )])
        self.assertIn("auto_123", out.getvalue())

    def test_list_canvases_calls_automation_canvases_endpoint(self):
        calls = []

        def fake_json_request(method, url, payload=None):
            calls.append((method, url, payload))
            return {"canvases": [{"id": "canvas123", "title": "kk"}]}

        out = StringIO()
        args = automation_cli.parse_args(["list-canvases", "--server", "http://127.0.0.1:3000"])

        with patch.object(automation_cli, "json_request", side_effect=fake_json_request):
            exit_code = automation_cli.list_canvases_command(args, stdout=out)

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, [("GET", "http://127.0.0.1:3000/api/automation/canvases", None)])
        self.assertIn("canvas123", out.getvalue())

    def test_list_canvas_workflows_calls_canvas_workflows_endpoint(self):
        calls = []

        def fake_json_request(method, url, payload=None):
            calls.append((method, url, payload))
            return {"workflows": [{"id": "wf_a", "name": "product-main"}]}

        out = StringIO()
        args = automation_cli.parse_args([
            "list-canvas-workflows",
            "--server", "http://127.0.0.1:3000",
            "--canvas", "canvas123",
        ])

        with patch.object(automation_cli, "json_request", side_effect=fake_json_request):
            exit_code = automation_cli.list_canvas_workflows_command(args, stdout=out)

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, [(
            "GET",
            "http://127.0.0.1:3000/api/automation/canvases/canvas123/workflows",
            None,
        )])
        self.assertIn("wf_a", out.getvalue())

    def test_run_no_wait_posts_canvas_id_and_prints_task_id(self):
        calls = []

        def fake_json_request(method, url, payload=None):
            calls.append((method, url, payload))
            return {"task_id": "auto_canvas", "status": "queued"}

        out = StringIO()
        args = automation_cli.parse_args([
            "run",
            "--server", "http://127.0.0.1:3000",
            "--canvas", "canvas123",
            "--image-url", "https://example.com/product.png",
            "--no-wait",
        ])

        with patch.object(automation_cli, "json_request", side_effect=fake_json_request):
            exit_code = automation_cli.run_command(args, stdout=out)

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls[0][2], {
            "canvas_id": "canvas123",
            "image_urls": ["https://example.com/product.png"],
            "callback_url": "",
        })
        self.assertIn("auto_canvas", out.getvalue())

    def test_run_canvas_workflow_posts_canvas_workflow_id(self):
        calls = []

        def fake_json_request(method, url, payload=None):
            calls.append((method, url, payload))
            return {"task_id": "auto_canvas", "status": "queued"}

        out = StringIO()
        args = automation_cli.parse_args([
            "run",
            "--server", "http://127.0.0.1:3000",
            "--canvas", "canvas123",
            "--canvas-workflow", "wf_a",
            "--image-url", "https://example.com/product.png",
            "--no-wait",
        ])

        with patch.object(automation_cli, "json_request", side_effect=fake_json_request):
            exit_code = automation_cli.run_command(args, stdout=out)

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls[0][2], {
            "canvas_id": "canvas123",
            "canvas_workflow_id": "wf_a",
            "image_urls": ["https://example.com/product.png"],
            "callback_url": "",
        })

    def test_run_rejects_workflow_and_canvas_workflow_together(self):
        with self.assertRaises(SystemExit) as ctx:
            automation_cli.parse_args([
                "run",
                "--workflow", "ecommerce-main",
                "--canvas-workflow", "wf_a",
                "--image-url", "https://example.com/product.png",
            ])

        self.assertIn("--canvas-workflow requires --canvas", str(ctx.exception))

    def test_run_uploads_image_file_and_posts_returned_url(self):
        calls = []

        def fake_json_request(method, url, payload=None):
            calls.append((method, url, payload))
            return {"task_id": "auto_123", "status": "queued"}

        def fake_upload_image_file(server, path):
            self.assertEqual(server, "http://127.0.0.1:3000")
            self.assertTrue(path.endswith("input.png"))
            return {"url": "/assets/input/input.png", "name": "input.png", "size": 10}

        out = StringIO()
        args = automation_cli.parse_args([
            "run",
            "--server", "http://127.0.0.1:3000",
            "--workflow", "ecommerce-main",
            "--image-url", "https://example.com/product.png",
            "--image-file", os.path.join(tempfile.gettempdir(), "input.png"),
            "--no-wait",
        ])

        with patch.object(automation_cli, "json_request", side_effect=fake_json_request), \
             patch.object(automation_cli, "upload_image_file", side_effect=fake_upload_image_file):
            exit_code = automation_cli.run_command(args, stdout=out)

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls[0][2]["image_urls"], [
            "https://example.com/product.png",
            "/assets/input/input.png",
        ])

    def test_upload_image_file_posts_multipart_to_upload_endpoint(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"url": "/assets/input/input.png"}'

        def fake_urlopen(req, timeout=60):
            captured["url"] = req.full_url
            captured["content_type"] = req.get_header("Content-type")
            captured["body"] = req.data
            captured["timeout"] = timeout
            return FakeResponse()

        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as f:
            f.write(b"png-bytes")
            path = f.name
        try:
            with patch.object(automation_cli.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = automation_cli.upload_image_file("http://127.0.0.1:3000", path)
        finally:
            os.remove(path)

        self.assertEqual(result["url"], "/assets/input/input.png")
        self.assertEqual(captured["url"], "http://127.0.0.1:3000/api/automation/upload")
        self.assertIn("multipart/form-data", captured["content_type"])
        self.assertIn(b'Content-Disposition: form-data; name="file"; filename=', captured["body"])
        self.assertIn(b"Content-Type: image/png", captured["body"])

    def test_image_file_missing_reports_clear_error(self):
        missing = os.path.join(tempfile.gettempdir(), "missing-automation-cli-input.png")
        if os.path.exists(missing):
            os.remove(missing)
        args = automation_cli.parse_args([
            "run",
            "--workflow", "ecommerce-main",
            "--image-file", missing,
            "--no-wait",
        ])

        with self.assertRaises(SystemExit) as ctx:
            automation_cli.run_command(args, stdout=StringIO())

        self.assertIn("Image file not found", str(ctx.exception))

    def test_run_rejects_canvas_and_workflow_together(self):
        with self.assertRaises(SystemExit):
            automation_cli.parse_args([
                "run",
                "--canvas", "canvas123",
                "--workflow", "ecommerce-main",
                "--image-url", "https://example.com/product.png",
            ])

    def test_run_requires_canvas_or_workflow(self):
        with self.assertRaises(SystemExit):
            automation_cli.parse_args([
                "run",
                "--image-url", "https://example.com/product.png",
            ])


if __name__ == "__main__":
    unittest.main()
