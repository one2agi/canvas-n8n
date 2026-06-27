import os
import sys
import unittest
import asyncio
import tempfile
import struct
import zlib
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import main


def png_bytes():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


PNG_BYTES = png_bytes()


class FakeStreamResponse:
    def __init__(self, content, content_type="image/png", chunks=None):
        self.content = content
        self.headers = {"content-type": content_type, "content-length": str(len(content))}
        self._chunks = chunks or [content]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class FakeAsyncClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url):
        return self.response


class AutomationWorkflowApiTests(unittest.TestCase):
    def setUp(self):
        main.AUTOMATION_WORKFLOW_TASKS.clear()
        main.AUTOMATION_TEST_CALLBACKS.clear()

    def test_lists_canvas_subworkflows_api(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "nodes": [
                {"id": "prompt_a", "type": "prompt", "x": 0, "y": 0},
                {"id": "gen_a", "type": "generator", "x": 200, "y": 0},
                {"id": "out_a", "type": "output", "x": 400, "y": 0},
                {"id": "img_b", "type": "image", "x": 0, "y": 400},
                {"id": "gen_b", "type": "generator", "x": 200, "y": 400},
                {"id": "out_b", "type": "output", "x": 400, "y": 400},
            ],
            "connections": [
                {"id": "c1", "from": "prompt_a", "to": "gen_a"},
                {"id": "c2", "from": "gen_a", "to": "out_a"},
                {"id": "c3", "from": "img_b", "to": "gen_b"},
                {"id": "c4", "from": "gen_b", "to": "out_b"},
            ],
        }

        with patch.object(main, "load_canvas", return_value=canvas):
            response = client.get("/api/automation/canvases/canvas123/workflows")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["canvas_id"], "canvas123")
        self.assertEqual(body["title"], "kk")
        self.assertEqual([item["workflow_id"] for item in body["workflows"]], ["workflow_1", "workflow_2"])

    def test_detected_workflow_key_is_stable_when_nodes_move(self):
        workflow = {
            "nodes": [
                {"id": "b_node", "type": "generator", "x": 100, "y": 300},
                {"id": "a_node", "type": "prompt", "x": 0, "y": 0},
            ],
            "connections": [{"id": "c1", "from": "a_node", "to": "b_node"}],
        }
        moved = {
            "nodes": [
                {"id": "b_node", "type": "generator", "x": 900, "y": 100},
                {"id": "a_node", "type": "prompt", "x": 800, "y": 100},
            ],
            "connections": workflow["connections"],
        }

        first = main.automation_detect_canvas_workflows(workflow)[0]
        second = main.automation_detect_canvas_workflows(moved)[0]

        self.assertEqual(first["workflow_key"], "f6a2a1c4a33448bf")
        self.assertEqual(first["legacy_workflow_key"], "2d5b5b0a2ddb3698")
        self.assertEqual(second["workflow_key"], first["workflow_key"])

    def test_detected_workflow_key_is_stable_when_node_is_added(self):
        workflow = {
            "nodes": [
                {"id": "b_node", "type": "generator", "x": 100, "y": 300},
                {"id": "a_node", "type": "prompt", "x": 0, "y": 0},
            ],
            "connections": [{"id": "c1", "from": "a_node", "to": "b_node"}],
        }
        added = {
            "automation_workflow_names": {
                "f6a2a1c4a33448bf": {"name": "dress-main", "updated_at": 1}
            },
            "nodes": workflow["nodes"] + [
                {"id": "new_api_node", "type": "generator", "x": 300, "y": 300},
            ],
            "connections": workflow["connections"] + [
                {"id": "c2", "from": "b_node", "to": "new_api_node"},
            ],
        }

        first = main.automation_detect_canvas_workflows(workflow)[0]
        second = main.automation_detect_canvas_workflows(added)[0]

        self.assertEqual(first["workflow_key"], "f6a2a1c4a33448bf")
        self.assertEqual(second["workflow_key"], first["workflow_key"])
        self.assertEqual(second["legacy_workflow_key"], "8205faccd10ca38c")
        self.assertEqual(second["name"], "dress-main")

    def test_canvas_workflows_include_saved_custom_name(self):
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "automation_workflow_names": {
                "2d5b5b0a2ddb3698": {"name": "dress-main", "updated_at": 1}
            },
            "nodes": [
                {"id": "b_node", "type": "generator", "x": 100, "y": 300},
                {"id": "a_node", "type": "prompt", "x": 0, "y": 0},
            ],
            "connections": [{"id": "c1", "from": "a_node", "to": "b_node"}],
        }

        with patch.object(main, "load_canvas", return_value=canvas):
            body = main.automation_canvas_workflow_records("canvas123")

        workflow = body["workflows"][0]
        self.assertEqual(workflow["workflow_key"], "f6a2a1c4a33448bf")
        self.assertEqual(workflow["legacy_workflow_key"], "2d5b5b0a2ddb3698")
        self.assertEqual(workflow["name"], "dress-main")
        self.assertEqual(workflow["custom_name"], "dress-main")
        self.assertEqual(workflow["label"], "dress-main · 2 节点 · 1 连线")

    def test_patch_canvas_workflow_name_saves_canvas(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "nodes": [
                {"id": "b_node", "type": "generator", "x": 100, "y": 300},
                {"id": "a_node", "type": "prompt", "x": 0, "y": 0},
            ],
            "connections": [{"id": "c1", "from": "a_node", "to": "b_node"}],
        }
        saved = []

        with patch.object(main, "load_canvas", return_value=canvas), \
             patch.object(main, "save_canvas", side_effect=lambda item: saved.append(item)):
            response = client.patch(
                "/api/automation/canvases/canvas123/workflows/f6a2a1c4a33448bf/name",
                json={"name": "dress-main"},
            )

        self.assertEqual(response.status_code, 200)
        saved_entry = saved[0]["automation_workflow_names"]["f6a2a1c4a33448bf"]
        self.assertEqual(saved_entry["name"], "dress-main")
        self.assertEqual(saved_entry["legacy_workflow_key"], "2d5b5b0a2ddb3698")
        self.assertEqual(saved_entry["anchor_node_id"], "b_node")
        self.assertEqual(saved_entry["node_ids"], ["a_node", "b_node"])
        self.assertEqual(response.json()["workflow"]["name"], "dress-main")

    def test_patch_canvas_workflow_name_accepts_legacy_key_and_migrates(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "automation_workflow_names": {
                "2d5b5b0a2ddb3698": {"name": "dress-main", "updated_at": 1}
            },
            "nodes": [
                {"id": "b_node", "type": "generator", "x": 100, "y": 300},
                {"id": "a_node", "type": "prompt", "x": 0, "y": 0},
            ],
            "connections": [{"id": "c1", "from": "a_node", "to": "b_node"}],
        }
        saved = []

        with patch.object(main, "load_canvas", return_value=canvas), \
             patch.object(main, "save_canvas", side_effect=lambda item: saved.append(item)):
            response = client.patch(
                "/api/automation/canvases/canvas123/workflows/2d5b5b0a2ddb3698/name",
                json={"name": "dress-updated"},
            )

        self.assertEqual(response.status_code, 200)
        names = saved[0]["automation_workflow_names"]
        self.assertNotIn("2d5b5b0a2ddb3698", names)
        self.assertEqual(names["f6a2a1c4a33448bf"]["name"], "dress-updated")

    def test_patch_canvas_workflow_name_rejects_duplicate_name(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "automation_workflow_names": {
                "bbd09abcf2d12fea": {"name": "dress-main", "updated_at": 1},
                "f6a2a1c4a33448bf": {"name": "other-main", "updated_at": 1},
            },
            "nodes": [
                {"id": "a_node", "type": "generator", "x": 0, "y": 0},
                {"id": "b_node", "type": "generator", "x": 400, "y": 0},
            ],
            "connections": [],
        }

        with patch.object(main, "load_canvas", return_value=canvas):
            response = client.patch(
                "/api/automation/canvases/canvas123/workflows/bbd09abcf2d12fea/name",
                json={"name": "other-main"},
            )

        self.assertEqual(response.status_code, 409)

    def test_patch_canvas_workflow_name_rejects_default_display_name_duplicate(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "nodes": [
                {"id": "a_node", "type": "generator", "x": 0, "y": 0},
                {"id": "b_node", "type": "generator", "x": 400, "y": 0},
            ],
            "connections": [],
        }

        with patch.object(main, "load_canvas", return_value=canvas):
            response = client.patch(
                "/api/automation/canvases/canvas123/workflows/bbd09abcf2d12fea/name",
                json={"name": "工作流 2"},
            )

        self.assertEqual(response.status_code, 409)

    def test_patch_canvas_workflow_name_returns_404_for_missing_workflow_key(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "nodes": [{"id": "a_node", "type": "generator", "x": 0, "y": 0}],
            "connections": [],
        }

        with patch.object(main, "load_canvas", return_value=canvas):
            response = client.patch(
                "/api/automation/canvases/canvas123/workflows/missingkey/name",
                json={"name": "dress-main"},
            )

        self.assertEqual(response.status_code, 404)

    def test_patch_canvas_workflow_name_clears_custom_name(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "automation_workflow_names": {
                "2d5b5b0a2ddb3698": {"name": "dress-main", "updated_at": 1}
            },
            "nodes": [
                {"id": "b_node", "type": "generator", "x": 100, "y": 300},
                {"id": "a_node", "type": "prompt", "x": 0, "y": 0},
            ],
            "connections": [{"id": "c1", "from": "a_node", "to": "b_node"}],
        }
        saved = []

        with patch.object(main, "load_canvas", return_value=canvas), \
             patch.object(main, "save_canvas", side_effect=lambda item: saved.append(item)):
            response = client.patch(
                "/api/automation/canvases/canvas123/workflows/2d5b5b0a2ddb3698/name",
                json={"name": "   "},
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("2d5b5b0a2ddb3698", saved[0]["automation_workflow_names"])
        self.assertEqual(response.json()["workflow"]["name"], "工作流 1")

    def test_create_workflow_run_loads_selected_canvas_subworkflow(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "nodes": [
                {"id": "prompt_a", "type": "prompt", "x": 0, "y": 0},
                {"id": "gen_a", "type": "generator", "x": 200, "y": 0},
                {"id": "out_a", "type": "output", "x": 400, "y": 0},
                {"id": "img_b", "type": "image", "x": 0, "y": 400},
                {"id": "gen_b", "type": "generator", "x": 200, "y": 400},
                {"id": "out_b", "type": "output", "x": 400, "y": 400},
            ],
            "connections": [
                {"id": "c1", "from": "prompt_a", "to": "gen_a"},
                {"id": "c2", "from": "gen_a", "to": "out_a"},
                {"id": "c3", "from": "img_b", "to": "gen_b"},
                {"id": "c4", "from": "gen_b", "to": "out_b"},
            ],
        }

        def fake_create_task(coro):
            coro.close()
            return object()

        with patch.object(main, "load_canvas", return_value=canvas), \
             patch.object(main.asyncio, "create_task", side_effect=fake_create_task):
            response = client.post("/api/automation/workflow-runs", json={
                "canvas_id": "canvas123",
                "canvas_workflow_id": "workflow_2",
                "image_urls": ["https://example.com/product.png"],
            })

        self.assertEqual(response.status_code, 200)
        task = main.AUTOMATION_WORKFLOW_TASKS[response.json()["task_id"]]
        self.assertEqual(task["canvas_workflow_id"], "workflow_2")
        self.assertEqual({node["id"] for node in task["workflow"]["nodes"]}, {"img_b", "gen_b", "out_b"})

    def test_create_workflow_run_loads_canvas_subworkflow_by_workflow_key(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "nodes": [
                {"id": "prompt_a", "type": "prompt", "x": 0, "y": 0},
                {"id": "gen_a", "type": "generator", "x": 200, "y": 0},
                {"id": "out_a", "type": "output", "x": 400, "y": 0},
            ],
            "connections": [
                {"id": "c1", "from": "prompt_a", "to": "gen_a"},
                {"id": "c2", "from": "gen_a", "to": "out_a"},
            ],
        }

        def fake_create_task(coro):
            coro.close()
            return object()

        with patch.object(main, "load_canvas", return_value=canvas), \
             patch.object(main.asyncio, "create_task", side_effect=fake_create_task):
            response = client.post("/api/automation/workflow-runs", json={
                "canvas_id": "canvas123",
                "canvas_workflow_id": "dfdbf54527499d49",
                "image_urls": ["https://example.com/product.png"],
            })

        self.assertEqual(response.status_code, 200)
        task = main.AUTOMATION_WORKFLOW_TASKS[response.json()["task_id"]]
        self.assertEqual(task["canvas_workflow_id"], "workflow_1")
        self.assertEqual(task["workflow"]["canvas_workflow_key"], "dfdbf54527499d49")

    def test_create_workflow_run_loads_selected_canvas_subworkflow_by_name(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "automation_workflow_names": {
                "01af8d2d4d6fa386": {"name": "dress-main", "updated_at": 1}
            },
            "nodes": [
                {"id": "img_a", "type": "image", "x": 0, "y": 0},
                {"id": "gen_a", "type": "generator", "x": 200, "y": 0},
                {"id": "out_a", "type": "output", "x": 400, "y": 0},
            ],
            "connections": [
                {"id": "c1", "from": "img_a", "to": "gen_a"},
                {"id": "c2", "from": "gen_a", "to": "out_a"},
            ],
        }

        def fake_create_task(coro):
            coro.close()
            return object()

        with patch.object(main, "load_canvas", return_value=canvas), \
             patch.object(main.asyncio, "create_task", side_effect=fake_create_task):
            response = client.post("/api/automation/workflow-runs", json={
                "canvas_id": "canvas123",
                "canvas_workflow_name": "dress-main",
                "image_urls": ["https://example.com/product.png"],
            })

        self.assertEqual(response.status_code, 200)
        task = main.AUTOMATION_WORKFLOW_TASKS[response.json()["task_id"]]
        self.assertEqual(task["canvas_workflow_name"], "dress-main")
        self.assertEqual(task["canvas_workflow_id"], "workflow_1")

    def test_create_workflow_run_returns_404_for_missing_canvas_workflow_name(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "kk",
            "nodes": [{"id": "gen_a", "type": "generator", "x": 0, "y": 0}],
            "connections": [],
        }

        with patch.object(main, "load_canvas", return_value=canvas):
            response = client.post("/api/automation/workflow-runs", json={
                "canvas_id": "canvas123",
                "canvas_workflow_name": "missing-name",
                "image_urls": ["https://example.com/product.png"],
            })

        self.assertEqual(response.status_code, 404)

    def test_run_uses_queued_workflow_snapshot_without_reloading_canvas(self):
        queued_workflow = {
            "format": "infinite-canvas-workflow",
            "nodes": [{"id": "gen_snapshot", "type": "generator"}],
            "connections": [],
        }
        payload = main.AutomationWorkflowRunRequest(
            canvas_id="canvas123",
            canvas_workflow_id="workflow_2",
            image_urls=["https://example.com/product.png"],
        )
        task_id = "auto_snapshot"
        main.AUTOMATION_WORKFLOW_TASKS[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "images": [],
            "error": "",
            "callback_url": "",
            "callback_error": "",
            "workflow_name": "",
            "canvas_id": payload.canvas_id,
            "canvas_workflow_id": payload.canvas_workflow_id,
            "workflow_source": "canvas",
            "created_at": 1,
            "updated_at": 1,
            "workflow": queued_workflow,
        }

        with patch.object(main, "automation_download_input_images", new=AsyncMock(return_value=[])), \
             patch.object(main, "load_canvas", side_effect=AssertionError("canvas should not reload")), \
             patch.object(main, "build_online_image_result", new=AsyncMock(return_value={"images": ["/assets/output/snapshot.png"]})):
            asyncio.run(main.run_automation_workflow_task(task_id, payload))

        task = main.AUTOMATION_WORKFLOW_TASKS[task_id]
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(task["images"], ["/assets/output/snapshot.png"])

    def test_automation_upload_saves_input_asset(self):
        client = TestClient(main.app)
        uploaded = PNG_BYTES

        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(main, "OUTPUT_INPUT_DIR", temp_dir):
            response = client.post(
                "/api/automation/upload",
                files={"file": ("product.png", uploaded, "image/png")},
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["url"].startswith("/assets/input/automation_"))
            self.assertEqual(body["name"], "product.png")
            saved_name = os.path.basename(body["url"])
            saved_path = os.path.join(temp_dir, saved_name)
            self.assertTrue(os.path.exists(saved_path))
            with open(saved_path, "rb") as f:
                self.assertEqual(f.read(), uploaded)

    def test_automation_upload_rejects_non_image(self):
        client = TestClient(main.app)

        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(main, "OUTPUT_INPUT_DIR", temp_dir):
            response = client.post(
                "/api/automation/upload",
                files={"file": ("not-image.txt", b"not an image", "text/plain")},
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(os.listdir(temp_dir), [])

    def test_automation_upload_rejects_oversized_image(self):
        client = TestClient(main.app)

        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(main, "OUTPUT_INPUT_DIR", temp_dir), \
             patch.object(main, "LOCAL_IMAGE_IMPORT_MAX_BYTES", len(PNG_BYTES) - 1):
            response = client.post(
                "/api/automation/upload",
                files={"file": ("product.png", PNG_BYTES, "image/png")},
            )

            self.assertEqual(response.status_code, 413)
            self.assertEqual(os.listdir(temp_dir), [])

    def test_prepare_input_images_accepts_internal_asset_url(self):
        with tempfile.TemporaryDirectory() as input_dir, \
             tempfile.TemporaryDirectory() as asset_output_dir, \
             tempfile.TemporaryDirectory() as output_dir, \
             patch.object(main, "OUTPUT_INPUT_DIR", input_dir), \
             patch.object(main, "OUTPUT_OUTPUT_DIR", asset_output_dir), \
             patch.object(main, "OUTPUT_DIR", output_dir):
            for root in (input_dir, asset_output_dir, output_dir):
                with open(os.path.join(root, "product.png"), "wb") as f:
                    f.write(PNG_BYTES)
            result = asyncio.run(main.automation_prepare_input_images([
                "/assets/input/product.png",
                "/assets/output/product.png",
                "/output/product.png",
            ]))

        self.assertEqual(result, [
            "/assets/input/product.png",
            "/assets/output/product.png",
            "/output/product.png",
        ])

    def test_prepare_input_images_rejects_unsupported_internal_asset_area(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(main, "OUTPUT_INPUT_DIR", temp_dir):
            with open(os.path.join(temp_dir, "product.png"), "wb") as f:
                f.write(PNG_BYTES)
            with self.assertRaises(main.HTTPException) as context:
                asyncio.run(main.automation_prepare_input_images(["/assets/library/product.png"]))

        self.assertEqual(context.exception.status_code, 400)

    def test_prepare_input_images_rejects_missing_internal_asset_url(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(main, "OUTPUT_INPUT_DIR", temp_dir):
            with self.assertRaises(main.HTTPException) as context:
                asyncio.run(main.automation_prepare_input_images(["/assets/input/missing.png"]))

        self.assertEqual(context.exception.status_code, 400)

    def test_prepare_input_images_rejects_non_image_internal_asset_url(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(main, "OUTPUT_INPUT_DIR", temp_dir):
            with open(os.path.join(temp_dir, "note.txt"), "wb") as f:
                f.write(b"not an image")
            with self.assertRaises(main.HTTPException) as context:
                asyncio.run(main.automation_prepare_input_images(["/assets/input/note.txt"]))

        self.assertEqual(context.exception.status_code, 400)

    def test_prepare_input_images_rejects_fake_png_internal_asset_url(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(main, "OUTPUT_INPUT_DIR", temp_dir):
            with open(os.path.join(temp_dir, "fake.png"), "wb") as f:
                f.write(b"not a real png")
            with self.assertRaises(main.HTTPException) as context:
                asyncio.run(main.automation_prepare_input_images(["/assets/input/fake.png"]))

        self.assertEqual(context.exception.status_code, 400)

    def test_prepare_input_images_rejects_remote_non_image_response_without_saving(self):
        fake_response = FakeStreamResponse(b"not an image", content_type="text/plain")

        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(main, "OUTPUT_INPUT_DIR", temp_dir), \
             patch.object(main.httpx, "AsyncClient", return_value=FakeAsyncClient(fake_response)):
            with self.assertRaises(main.HTTPException) as context:
                asyncio.run(main.automation_prepare_input_images(["https://example.com/fake.png"]))

            self.assertEqual(os.listdir(temp_dir), [])

        self.assertEqual(context.exception.status_code, 400)

    def test_prepare_input_images_rejects_remote_oversized_response_without_saving(self):
        fake_response = FakeStreamResponse(
            PNG_BYTES + b"x",
            content_type="image/png",
            chunks=[PNG_BYTES, b"x"],
        )

        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(main, "OUTPUT_INPUT_DIR", temp_dir), \
             patch.object(main, "LOCAL_IMAGE_IMPORT_MAX_BYTES", len(PNG_BYTES)), \
             patch.object(main.httpx, "AsyncClient", return_value=FakeAsyncClient(fake_response)):
            with self.assertRaises(main.HTTPException) as context:
                asyncio.run(main.automation_prepare_input_images(["https://example.com/product.png"]))

            self.assertEqual(os.listdir(temp_dir), [])

        self.assertEqual(context.exception.status_code, 413)

    def test_prepare_input_images_rejects_encoded_internal_traversal(self):
        urls = [
            "/assets/input/%2e%2e/output/a.png",
            "/assets/input/%252e%252e/output/a.png",
            "/assets/input/%5c..%5coutput/a.png",
        ]
        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(main.HTTPException) as context:
                    asyncio.run(main.automation_prepare_input_images([url]))

                self.assertEqual(context.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
