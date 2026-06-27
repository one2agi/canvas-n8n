import os
import sys
import unittest
import asyncio
import tempfile
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import main


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

        with patch.object(main, "automation_prepare_input_images", new=AsyncMock(return_value=[])), \
             patch.object(main, "load_canvas", side_effect=AssertionError("canvas should not reload")), \
             patch.object(main, "build_online_image_result", new=AsyncMock(return_value={"images": ["/assets/output/snapshot.png"]})):
            asyncio.run(main.run_automation_workflow_task(task_id, payload))

        task = main.AUTOMATION_WORKFLOW_TASKS[task_id]
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(task["images"], ["/assets/output/snapshot.png"])

    def test_automation_upload_saves_input_asset(self):
        client = TestClient(main.app)
        uploaded = b"fake-image-bytes"

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

    def test_prepare_input_images_accepts_internal_asset_url(self):
        result = asyncio.run(main.automation_prepare_input_images(["/assets/input/product.png"]))

        self.assertEqual(result, ["/assets/input/product.png"])

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
