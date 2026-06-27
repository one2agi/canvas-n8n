import os
import sys
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
