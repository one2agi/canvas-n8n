import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import main


class AutomationLlmUserInputTests(unittest.TestCase):
    def setUp(self):
        main.AUTOMATION_WORKFLOW_TASKS.clear()
        main.AUTOMATION_TEST_CALLBACKS.clear()

    def test_run_passes_api_llm_user_input_to_image_only_llm_workflow(self):
        workflow = {
            "format": "infinite-canvas-workflow",
            "nodes": [
                {"id": "group_images", "type": "group", "items": ["img_a", "img_b"]},
                {"id": "img_a", "type": "image", "name": "产品图"},
                {"id": "img_b", "type": "image", "name": "参考图"},
                {"id": "llm_node", "type": "llm", "systemPrompt": "系统提示词", "outputFormat": "json"},
                {"id": "json_node", "type": "json-splitter"},
                {"id": "gen_one", "type": "generator"},
                {"id": "gen_two", "type": "generator"},
                {"id": "out", "type": "output"},
            ],
            "connections": [
                {"id": "c1", "from": "group_images", "to": "llm_node"},
                {"id": "c2", "from": "llm_node", "to": "json_node"},
                {"id": "c3", "from": "json_node", "fromPort": 0, "to": "gen_one"},
                {"id": "c4", "from": "json_node", "fromPort": 1, "to": "gen_two"},
                {"id": "c5", "from": "group_images", "to": "gen_one"},
                {"id": "c6", "from": "group_images", "to": "gen_two"},
                {"id": "c7", "from": "gen_one", "to": "out"},
                {"id": "c8", "from": "gen_two", "to": "out"},
            ],
        }
        payload = main.AutomationWorkflowRunRequest(
            workflow=workflow,
            image_urls=["https://example.com/product.png", "https://example.com/reference.png"],
            llm_user_input="请分析上传商品图片，生成2张差异化详情页生图prompt。",
        )
        task_id = "auto_llm_input"
        main.AUTOMATION_WORKFLOW_TASKS[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "images": [],
            "error": "",
            "callback_url": "",
            "callback_error": "",
            "workflow_name": "",
            "canvas_id": "",
            "canvas_workflow_id": "",
            "workflow_source": "inline",
            "created_at": 1,
            "updated_at": 1,
            "workflow": workflow,
        }
        captured_llm = []
        captured_generators = []

        async def fake_canvas_llm(request):
            captured_llm.append(request)
            return {"text": '{"prompts":[{"prompt":"首图prompt"},{"prompt":"详情prompt"}]}'}

        async def fake_build_online_image_result(request):
            captured_generators.append(request)
            return {"images": [f"/assets/output/{len(captured_generators)}.png"]}

        with patch.object(main, "automation_download_input_images", new=AsyncMock(return_value=[
            "/assets/input/product.png",
            "/assets/input/reference.png",
        ])), \
             patch.object(main, "canvas_llm", new=AsyncMock(side_effect=fake_canvas_llm)), \
             patch.object(main, "build_online_image_result", new=AsyncMock(side_effect=fake_build_online_image_result)):
            asyncio.run(main.run_automation_workflow_task(task_id, payload))

        task = main.AUTOMATION_WORKFLOW_TASKS[task_id]
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(captured_llm[0].message, "请分析上传商品图片，生成2张差异化详情页生图prompt。")
        self.assertEqual(captured_llm[0].system_prompt, "系统提示词")
        self.assertEqual(captured_llm[0].images, ["/assets/input/product.png", "/assets/input/reference.png"])
        self.assertEqual([item.prompt for item in captured_generators], ["首图prompt", "详情prompt"])
        self.assertEqual(
            [[ref.url for ref in item.reference_images] for item in captured_generators],
            [["/assets/input/product.png", "/assets/input/reference.png"], ["/assets/input/product.png", "/assets/input/reference.png"]],
        )

    def test_automation_generator_caps_reference_images_for_live_image_model(self):
        workflow = {
            "format": "infinite-canvas-workflow",
            "nodes": [
                {"id": "group_images", "type": "group", "items": [f"img_{index}" for index in range(8)]},
                *[
                    {"id": f"img_{index}", "type": "image", "url": f"/assets/input/{index}.png", "name": f"产品图{index}"}
                    for index in range(8)
                ],
                {"id": "json_node", "type": "json-splitter", "sourceItems": ["首图prompt"]},
                {"id": "gen_one", "type": "generator"},
            ],
            "connections": [
                {"id": "c1", "from": "group_images", "to": "gen_one"},
                {"id": "c2", "from": "json_node", "fromPort": 0, "to": "gen_one"},
            ],
        }

        request = main.automation_build_generator_request(workflow, workflow["nodes"][-1])

        self.assertEqual(request.prompt, "首图prompt")
        self.assertEqual([ref.url for ref in request.reference_images], [
            "/assets/input/0.png",
            "/assets/input/1.png",
            "/assets/input/2.png",
            "/assets/input/3.png",
            "/assets/input/4.png",
            "/assets/input/5.png",
        ])


if __name__ == "__main__":
    unittest.main()
