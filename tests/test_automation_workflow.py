import json
import os
import sys
import unittest
import asyncio
import tempfile
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import main


class AutomationWorkflowTests(unittest.TestCase):
    def setUp(self):
        main.AUTOMATION_WORKFLOW_TASKS.clear()
        main.AUTOMATION_TEST_CALLBACKS.clear()

    def test_detects_canvas_subworkflows_like_frontend(self):
        workflow = {
            "nodes": [
                {"id": "prompt_a", "type": "prompt", "x": 0, "y": 0},
                {"id": "gen_a", "type": "generator", "x": 200, "y": 0},
                {"id": "out_a", "type": "output", "x": 400, "y": 0},
                {"id": "img_b", "type": "image", "x": 0, "y": 400},
                {"id": "llm_b", "type": "llm", "x": 200, "y": 400},
                {"id": "split_b", "type": "json-splitter", "x": 400, "y": 400},
                {"id": "gen_b1", "type": "generator", "x": 600, "y": 300},
                {"id": "gen_b2", "type": "generator", "x": 600, "y": 500},
                {"id": "out_b", "type": "output", "x": 800, "y": 400},
            ],
            "connections": [
                {"id": "c1", "from": "prompt_a", "to": "gen_a"},
                {"id": "c2", "from": "gen_a", "to": "out_a"},
                {"id": "c3", "from": "img_b", "to": "llm_b"},
                {"id": "c4", "from": "llm_b", "to": "split_b"},
                {"id": "c5", "from": "split_b", "fromPort": 1, "to": "gen_b2"},
                {"id": "c6", "from": "split_b", "fromPort": 0, "to": "gen_b1"},
                {"id": "c7", "from": "gen_b1", "to": "out_b"},
                {"id": "c8", "from": "gen_b2", "to": "out_b"},
            ],
        }

        workflows = main.automation_detect_canvas_workflows(workflow)

        self.assertEqual([item["workflow_id"] for item in workflows], ["workflow_1", "workflow_2"])
        self.assertEqual(workflows[0]["run_order"], ["gen_a"])
        self.assertEqual(workflows[1]["run_order"], ["llm_b", "split_b", "gen_b1", "gen_b2"])
        self.assertEqual(workflows[1]["input_image_count"], 1)
        self.assertEqual(workflows[1]["output_node_count"], 1)

    def test_detected_run_order_preserves_splitter_port_order_through_prompt_nodes(self):
        workflow = {
            "nodes": [
                {"id": "llm", "type": "llm", "x": 0, "y": 0},
                {"id": "split", "type": "json-splitter", "x": 200, "y": 0},
                {"id": "prompt_a", "type": "prompt", "x": 400, "y": 0},
                {"id": "gen_a", "type": "generator", "x": 800, "y": 0},
                {"id": "gen_b", "type": "generator", "x": 600, "y": 0},
            ],
            "connections": [
                {"id": "c1", "from": "llm", "to": "split"},
                {"id": "c2", "from": "split", "fromPort": 0, "to": "prompt_a"},
                {"id": "c3", "from": "prompt_a", "to": "gen_a"},
                {"id": "c4", "from": "split", "fromPort": 1, "to": "gen_b"},
            ],
        }

        workflows = main.automation_detect_canvas_workflows(workflow)

        self.assertEqual(workflows[0]["run_order"], ["llm", "split", "gen_a", "gen_b"])

    def test_detected_workflows_ignore_non_list_group_items(self):
        workflow = {
            "nodes": [
                {"id": "group_1", "type": "group", "items": "b", "x": 0, "y": 0},
                {"id": "gen_a", "type": "generator", "x": 100, "y": 0},
                {"id": "b", "type": "generator", "x": 600, "y": 0},
            ],
            "connections": [
                {"id": "c1", "from": "group_1", "to": "gen_a"},
            ],
        }

        workflows = main.automation_detect_canvas_workflows(workflow)

        self.assertEqual([item["run_order"] for item in workflows], [["gen_a"], ["b"]])

    def test_canvas_subworkflow_payload_filters_duplicate_connection_ids_by_endpoints(self):
        workflow = {
            "nodes": [
                {"id": "prompt_a", "type": "prompt", "x": 0, "y": 0},
                {"id": "gen_a", "type": "generator", "x": 100, "y": 0},
                {"id": "prompt_b", "type": "prompt", "x": 500, "y": 0},
                {"id": "gen_b", "type": "generator", "x": 600, "y": 0},
            ],
            "connections": [
                {"id": "dup", "from": "prompt_a", "to": "gen_a"},
                {"id": "dup", "from": "prompt_b", "to": "gen_b"},
            ],
        }

        selected = main.automation_canvas_subworkflow_payload(workflow, "workflow_1")

        self.assertEqual(
            [(conn["from"], conn["to"]) for conn in selected["connections"]],
            [("prompt_a", "gen_a")],
        )

    def test_detected_workflows_tolerate_malformed_coordinates(self):
        workflow = {
            "nodes": [
                {"id": "gen_bad", "type": "generator", "x": "bad", "y": None, "w": "wide", "h": "tall"},
            ],
            "connections": [],
        }

        workflows = main.automation_detect_canvas_workflows(workflow)

        self.assertEqual(workflows[0]["run_order"], ["gen_bad"])
        self.assertEqual(workflows[0]["bounds"], {"x": 0, "y": 0, "w": 260, "h": 200})

    def test_canvas_subworkflow_payload_contains_only_selected_component(self):
        workflow = {
            "format": "infinite-canvas-workflow",
            "nodes": [
                {"id": "prompt_a", "type": "prompt", "x": 0, "y": 0},
                {"id": "gen_a", "type": "generator", "x": 200, "y": 0},
                {"id": "out_a", "type": "output", "x": 400, "y": 0},
                {"id": "img_b", "type": "image", "x": 0, "y": 400},
                {"id": "llm_b", "type": "llm", "x": 200, "y": 400},
                {"id": "gen_b", "type": "generator", "x": 400, "y": 400},
                {"id": "out_b", "type": "output", "x": 600, "y": 400},
            ],
            "connections": [
                {"id": "c1", "from": "prompt_a", "to": "gen_a"},
                {"id": "c2", "from": "gen_a", "to": "out_a"},
                {"id": "c3", "from": "img_b", "to": "llm_b"},
                {"id": "c4", "from": "llm_b", "to": "gen_b"},
                {"id": "c5", "from": "gen_b", "to": "out_b"},
            ],
        }

        selected = main.automation_canvas_subworkflow_payload(workflow, "workflow_2")

        self.assertEqual(
            {node["id"] for node in selected["nodes"]},
            {"img_b", "llm_b", "gen_b", "out_b"},
        )
        self.assertEqual(
            {conn["id"] for conn in selected["connections"]},
            {"c3", "c4", "c5"},
        )

    def test_extracts_prompt_items_from_nested_prompt_array(self):
        source = json.dumps({
            "meta": {"ignored": True},
            "result": {
                "image_prompts": [
                    {"content": "首图 prompt"},
                    {"prompt": "细节 prompt"},
                    "场景 prompt",
                ]
            },
        }, ensure_ascii=False)

        self.assertEqual(
            main.automation_parse_json_prompt_items(source),
            ["首图 prompt", "细节 prompt", "场景 prompt"],
        )

    def test_extracts_prompt_items_from_markdown_json_fence(self):
        source = """```json
{
  "prompts": [
    {"image_no": 1, "type": "main", "prompt": "prompt one"},
    {"image_no": 2, "type": "detail", "prompt": "prompt two"},
    {"image_no": 3, "type": "scene", "prompt": "prompt three"},
    {"image_no": 4, "type": "craft", "prompt": "prompt four"},
    {"image_no": 5, "type": "trust", "prompt": "prompt five"}
  ]
}
```"""

        self.assertEqual(
            main.automation_parse_json_prompt_items(source),
            ["prompt one", "prompt two", "prompt three", "prompt four", "prompt five"],
        )

    def test_extracts_prompt_items_from_top_level_numbered_prompt_keys(self):
        source = json.dumps({
            "prompt_10": "prompt ten",
            "prompt_2": "prompt two",
            "prompt_1": "prompt one",
        }, ensure_ascii=False)

        self.assertEqual(
            main.automation_parse_json_prompt_items(source),
            ["prompt one", "prompt two", "prompt ten"],
        )

    def test_extracts_prompt_items_from_markdown_prompt_sections(self):
        source = """## Prompt 1：首图 / 点击图
第一张完整 prompt。

## Prompt 2：卖点证明图 A
第二张完整 prompt。

## Prompt 3：场景价值图
第三张完整 prompt。
"""

        self.assertEqual(
            main.automation_parse_json_prompt_items(source),
            ["第一张完整 prompt。", "第二张完整 prompt。", "第三张完整 prompt。"],
        )

    def test_extracts_longest_text_from_object_value_with_no_canonical_key(self):
        # 真实用户 case：Prompt_1 的 value 是对象 {无文字主图版, 带文字广告版}，
        # 两个键都不在 (content, prompt, text, description) 名单里。
        # 旧逻辑：JSON.stringify 整个对象 → 下游拿到的是 JSON dump，不是可用 prompt。
        # 正确行为：从对象的字符串值里选**最长**的（最长 = 最有可能是完整 prompt）。
        source = json.dumps({
            "工作流程": {
                "1_图片识别": [{"图片编号": "1"}],
                "7_5个最终生图Prompt": {
                    "Prompt_1_首图_点击图": {
                        "无文字主图版": "1:1 短文本",
                        "带文字广告版": "1:1 这是更长更详细的 prompt，包含更多细节描述和视觉规则",
                    },
                    "Prompt_2_卖点证明图A": "1:1 卖点证明图纯文本",
                    "Prompt_3_场景价值图": "1:1 场景图纯文本",
                    "Prompt_4_细节结构图": "1:1 细节图纯文本",
                    "Prompt_5_人群_信任收尾图": "1:1 人群图纯文本",
                },
            },
        }, ensure_ascii=False)

        items = main.automation_parse_json_prompt_items(source)
        self.assertEqual(len(items), 5)
        # 第 0 项应该是 Prompt_1 中两个版本里更长的那个（带文字广告版），不是 JSON dump
        self.assertIn("这是更长更详细的 prompt", items[0])
        self.assertNotIn("无文字主图版", items[0])  # 确认是文本不是键名
        self.assertNotIn("带文字广告版", items[0])  # 确认是文本不是键名
        self.assertNotIn("{}", items[0])  # 确认不是 JSON dump
        self.assertNotIn("\"无文字主图版\"", items[0])  # 确认不是 JSON dump
        # 第 1-4 项是纯文本，照常通过
        self.assertEqual(items[1], "1:1 卖点证明图纯文本")
        self.assertEqual(items[2], "1:1 场景图纯文本")
        self.assertEqual(items[3], "1:1 细节图纯文本")
        self.assertEqual(items[4], "1:1 人群图纯文本")

    def test_extracts_prompt_items_from_object_form_prompt_container(self):
        # LLM 返回：5 个 prompt 装在对象 7_5个最终生图Prompt 里（键名 Prompt_1..Prompt_5），
        # 顶层还有别的"图片识别"/"主图规划"等干扰数组，算法必须识别对象型容器而不是退化成 1 个端口。
        source = json.dumps({
            "工作流程": {
                "1_图片识别": [{"图片编号": "1", "角色": "产品图"}],
                "2_产品事实总结": {"产品名称": "女款连衣裙"},
                "6_5张主图规划": [
                    {"图片序号": "1", "类型": "首图"},
                    {"图片序号": "2", "类型": "卖点"},
                    {"图片序号": "3", "类型": "场景"},
                    {"图片序号": "4", "类型": "细节"},
                    {"图片序号": "5", "类型": "人群"},
                ],
                "7_5个最终生图Prompt": {
                    "Prompt_1_首图": "第一张图完整 prompt",
                    "Prompt_2_卖点": "第二张图完整 prompt",
                    "Prompt_3_场景": "第三张图完整 prompt",
                    "Prompt_4_细节": "第四张图完整 prompt",
                    "Prompt_5_人群": "第五张图完整 prompt",
                },
            },
        }, ensure_ascii=False)

        items = main.automation_parse_json_prompt_items(source)
        self.assertEqual(len(items), 5)

    def test_injects_downloaded_images_into_upstream_image_nodes(self):
        workflow = {
            "format": "infinite-canvas-workflow",
            "nodes": [
                {"id": "img_a", "type": "image", "url": "", "name": "上传节点"},
                {"id": "img_b", "type": "image", "url": "/assets/input/old.png", "name": "旧图"},
                {"id": "group_1", "type": "group", "items": ["img_a", "img_b"]},
                {"id": "llm_1", "type": "llm"},
                {"id": "gen_1", "type": "generator", "inputs": ["group_1:img_a"]},
            ],
            "connections": [
                {"from": "group_1", "to": "llm_1"},
                {"from": "group_1", "to": "gen_1"},
            ],
        }

        result = main.automation_apply_input_images(
            workflow,
            ["/assets/input/new.png"],
        )

        nodes = {node["id"]: node for node in result["nodes"]}
        self.assertEqual(nodes["img_a"]["url"], "/assets/input/new.png")
        self.assertEqual(nodes["img_a"]["mediaKind"], "image")
        self.assertEqual(nodes["img_a"]["name"], "new.png")
        self.assertEqual(nodes["img_b"]["url"], "/assets/input/old.png")

    def test_finds_cascade_order_for_terminal_generator(self):
        workflow = {
            "nodes": [
                {"id": "llm_1", "type": "llm"},
                {"id": "split_1", "type": "json-splitter"},
                {"id": "gen_1", "type": "generator"},
            ],
            "connections": [
                {"from": "llm_1", "to": "split_1"},
                {"from": "split_1", "to": "gen_1"},
            ],
        }

        self.assertEqual(
            main.automation_compute_run_order(workflow, "gen_1"),
            ["llm_1", "split_1", "gen_1"],
        )

    def test_create_workflow_run_queues_task_and_exposes_status(self):
        client = TestClient(main.app)
        payload = {
            "workflow": {
                "format": "infinite-canvas-workflow",
                "nodes": [{"id": "gen_1", "type": "generator"}],
                "connections": [],
            },
            "image_urls": ["https://example.com/product.png"],
            "callback_url": "http://127.0.0.1:3000/api/automation/test-callback",
        }

        def fake_create_task(coro):
            coro.close()
            return object()

        with patch.object(main.asyncio, "create_task", side_effect=fake_create_task):
            response = client.post("/api/automation/workflow-runs", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["task_id"].startswith("auto_"))
        self.assertEqual(body["status"], "queued")

        status_response = client.get(f"/api/automation/workflow-runs/{body['task_id']}")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "queued")

    def test_lists_automation_workflow_presets(self):
        client = TestClient(main.app)
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, "ecommerce-main.json"), "w", encoding="utf-8") as f:
                json.dump({"format": "infinite-canvas-workflow", "nodes": [], "connections": []}, f)
            with open(os.path.join(temp_dir, "notes.txt"), "w", encoding="utf-8") as f:
                f.write("ignored")

            with patch.object(main, "AUTOMATION_WORKFLOW_DIR", temp_dir):
                response = client.get("/api/automation/workflows")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflows"], [{"name": "ecommerce-main", "filename": "ecommerce-main.json"}])

    def test_create_workflow_run_loads_named_preset(self):
        client = TestClient(main.app)
        workflow = {
            "format": "infinite-canvas-workflow",
            "nodes": [{"id": "gen_1", "type": "generator"}],
            "connections": [],
        }

        def fake_create_task(coro):
            coro.close()
            return object()

        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, "ecommerce-main.json"), "w", encoding="utf-8") as f:
                json.dump(workflow, f)
            with patch.object(main, "AUTOMATION_WORKFLOW_DIR", temp_dir), \
                 patch.object(main.asyncio, "create_task", side_effect=fake_create_task):
                response = client.post("/api/automation/workflow-runs", json={
                    "workflow_name": "ecommerce-main",
                    "image_urls": ["https://example.com/product.png"],
                    "callback_url": "http://127.0.0.1:3000/api/automation/test-callback",
                })

        self.assertEqual(response.status_code, 200)
        task_id = response.json()["task_id"]
        self.assertEqual(main.AUTOMATION_WORKFLOW_TASKS[task_id]["workflow"], workflow)

    def test_resolves_workflow_from_saved_canvas_id(self):
        canvas = {
            "id": "canvas123",
            "title": "电商主图工作流",
            "nodes": [{"id": "gen_1", "type": "generator"}],
            "connections": [{"from": "gen_1", "to": "out_1"}],
        }
        payload = main.AutomationWorkflowRunRequest(canvas_id="canvas123")

        with patch.object(main, "load_canvas", return_value=canvas):
            workflow = main.automation_resolve_workflow(payload)

        self.assertEqual(workflow, {
            "format": "infinite-canvas-workflow",
            "nodes": canvas["nodes"],
            "connections": canvas["connections"],
        })

    def test_lists_automation_canvases(self):
        client = TestClient(main.app)
        records = [{
            "id": "canvas123",
            "title": "电商主图工作流",
            "kind": "classic",
            "node_count": 7,
            "updated_at": 1782470000000,
            "created_at": 1782460000000,
        }]

        with patch.object(main, "list_canvases", return_value=records):
            response = client.get("/api/automation/canvases")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["canvases"], [{
            "id": "canvas123",
            "title": "电商主图工作流",
            "kind": "classic",
            "node_count": 7,
            "updated_at": 1782470000000,
        }])

    def test_create_workflow_run_loads_saved_canvas(self):
        client = TestClient(main.app)
        canvas = {
            "id": "canvas123",
            "title": "电商主图工作流",
            "nodes": [{"id": "gen_1", "type": "generator"}],
            "connections": [],
        }

        def fake_create_task(coro):
            coro.close()
            return object()

        with patch.object(main, "load_canvas", return_value=canvas), \
             patch.object(main.asyncio, "create_task", side_effect=fake_create_task):
            response = client.post("/api/automation/workflow-runs", json={
                "canvas_id": "canvas123",
                "image_urls": ["https://example.com/product.png"],
            })

        self.assertEqual(response.status_code, 200)
        task_id = response.json()["task_id"]
        task = main.AUTOMATION_WORKFLOW_TASKS[task_id]
        self.assertEqual(task["workflow_source"], "canvas")
        self.assertEqual(task["canvas_id"], "canvas123")
        self.assertEqual(task["workflow"]["nodes"], canvas["nodes"])

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

    def test_local_test_callback_stores_payload(self):
        client = TestClient(main.app)

        response = client.post(
            "/api/automation/test-callback",
            json={"task_id": "auto_test", "status": "succeeded", "images": ["/assets/output/a.png"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)
        self.assertEqual(main.AUTOMATION_TEST_CALLBACKS[-1]["task_id"], "auto_test")

    def test_chat_endpoint_returns_stripped_text(self):
        """Regression: POST /api/chat must strip <think>...</think> from the
        assistant's text reply (not just JSON mode).
        Bug site: main.py:14318 (build_conversation_chat_reply still un-stripped)."""
        import httpx

        client = TestClient(main.app)

        think_block = "<think>The user just said hello. I'll respond politely.</think>\n"
        clean_reply = "你好！有什么可以帮你的吗？"

        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "choices": [{
                        "message": {"content": think_block + clean_reply}
                    }],
                    "usage": {"total_tokens": 42},
                }

            def raise_for_status(self):
                pass

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, *args, **kwargs):
                return FakeResponse()

        with patch.object(main, "resolve_chat_provider", return_value=("http://test", {}, "test-model")), \
             patch.object(httpx, "AsyncClient", FakeClient):
            response = client.post(
                "/api/chat",
                headers={"x-user-id": "test_text_strip"},
                json={
                    "message": "hello",
                    "provider": "comfly",
                    "model": "gpt-4o-mini",
                },
            )

        self.assertEqual(response.status_code, 200, f"got {response.status_code}: {response.text[:200]}")
        body = response.json()
        assistant = body.get("message") or {}
        content = assistant.get("content", "")
        self.assertNotIn("<think>", content, f"text leaked think block: {content[:200]}")
        self.assertNotIn("</think>", content, f"text leaked think block: {content[:200]}")
        self.assertIn(clean_reply, content, f"expected clean reply in: {content[:200]}")

    def test_decide_chat_agent_action_raises_on_httpx_error(self):
        """Regression: decide_chat_agent_action should raise HTTPException on LLM
        network failure instead of silently returning heuristic fallback.
        Bug site: main.py:9515-9518 (silent except Exception → return fallback)."""
        import httpx
        from fastapi import HTTPException

        payload = main.ChatRequest(
            message="hello",
            provider="comfly",
            model="gpt-4o-mini",
        )
        conversation = {
            "id": "conv1",
            "title": "test",
            "messages": [],
            "created_at": 0,
            "updated_at": 0,
        }

        class FailingClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, *args, **kwargs):
                raise httpx.ConnectError("simulated network failure")

        with patch.object(main, "resolve_chat_provider", return_value=("http://test", {}, "test-model")), \
             patch.object(httpx, "AsyncClient", FailingClient):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(main.decide_chat_agent_action(payload, conversation, []))

        self.assertEqual(
            ctx.exception.status_code, 502,
            f"Expected 502 from LLM network error, got {ctx.exception.status_code}: {ctx.exception.detail}",
        )

    def test_canvas_llm_json_mode_detects_truncation_by_finish_reason_length(self):
        """Regression: when LLM response is truncated by max_tokens (finish_reason=length),
        the canvas_llm endpoint must report 「截断」 + max_tokens hint, not generic
        「未返回合法 JSON」. Bug site: main.py:13000-13008.
        User case: prompt asks for 5 detailed prompts, response ~6000+ tokens,
        LLM_MAX_TOKENS=4096 truncates mid-JSON, user sees confusing error."""
        import httpx

        client = TestClient(main.app)

        # 模拟「用户大 JSON 被 max_tokens=4096 截断」的情况：
        # 响应 finish_reason=length, content 是中途断的 JSON 字符串
        truncated_content = '{"产品事实总结":{"产品名称":"豹纹印花短袖连衣裙（推测名称）","结构":"V领+短袖+抽绳腰+A字裙摆+'

        class TruncatedResponse:
            status_code = 200
            content = b'{"choices":[{"message":{"content":"' + truncated_content.encode() + b'"},"finish_reason":"length"}],"usage":{"total_tokens":4096}}'

            def json(self):
                return {
                    "choices": [{
                        "message": {"content": truncated_content},
                        "finish_reason": "length",   # 关键：被截断
                    }],
                    "usage": {"total_tokens": 4096, "completion_tokens": 4096},
                }

            def raise_for_status(self):
                pass

        class TruncatedClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, *args, **kwargs):
                return TruncatedResponse()

        with patch.object(main, "resolve_chat_provider", return_value=("http://test", {}, "test-model")), \
             patch.object(httpx, "AsyncClient", TruncatedClient):
            response = client.post(
                "/api/canvas-llm",
                json={
                    "message": "生成 5 张主图 prompt",
                    "provider": "comfly",
                    "model": "gpt-4o-mini",
                    "output_format": "json",
                },
            )

        self.assertEqual(response.status_code, 422, f"expected 422, got {response.status_code}: {response.text[:200]}")
        detail = response.json().get("detail", "")
        # 关键：必须告诉用户「截断」+「max_tokens」
        self.assertIn("截断", detail, f"error should mention 截断, got: {detail}")
        self.assertIn("max_tokens", detail, f"error should mention max_tokens, got: {detail}")

    def test_canvas_llm_json_mode_invalid_json_still_reports_actual_error(self):
        """回归：当 finish_reason=stop（未被截断）但 LLM 返回了非 JSON 内容时，
        错误信息应保留异常类型 + 截断的 JSON 内容，便于用户诊断。"""
        import httpx

        client = TestClient(main.app)

        garbage_content = "好的，我分析了图片。结论是：白底印花连衣裙。"

        class InvalidJsonResponse:
            status_code = 200
            content = b'{"choices":[{"message":{"content":"' + garbage_content.encode() + b'"},"finish_reason":"stop"}],"usage":{"total_tokens":50}}'

            def json(self):
                return {
                    "choices": [{
                        "message": {"content": garbage_content},
                        "finish_reason": "stop",   # 正常完成但内容不是 JSON
                    }],
                    "usage": {"total_tokens": 50},
                }

            def raise_for_status(self):
                pass

        class InvalidJsonClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, *args, **kwargs):
                return InvalidJsonResponse()

        with patch.object(main, "resolve_chat_provider", return_value=("http://test", {}, "test-model")), \
             patch.object(httpx, "AsyncClient", InvalidJsonClient):
            response = client.post(
                "/api/canvas-llm",
                json={
                    "message": "生成 JSON",
                    "provider": "comfly",
                    "model": "gpt-4o-mini",
                    "output_format": "json",
                },
            )

        self.assertEqual(response.status_code, 422)
        detail = response.json().get("detail", "")
        self.assertIn("未返回合法 JSON", detail)
        # 截断标志不应出现在正常 stop 的错误里
        self.assertNotIn("截断", detail)

    def test_chat_agent_endpoint_returns_502_on_llm_error(self):
        """Regression: POST /api/chat/agent must return 502 (not 200 with fake
        decision) when the LLM intent-router call fails.
        Bug site: main.py:9515-9518 + chat_agent caller at line 14354.

        We mock build_chat_text_reply to succeed so the test isolates the
        router's behavior: with the bug, decide_chat_agent_action silently
        returns a heuristic fallback and the endpoint returns 200. With the
        fix, decide_chat_agent_action raises HTTPException(502)."""
        import httpx

        client = TestClient(main.app)

        class FailingClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, *args, **kwargs):
                raise httpx.ConnectError("simulated network failure")

        async def fake_build_chat_text_reply(payload, conversation):
            return {
                "id": "fake_id",
                "role": "assistant",
                "content": "fake reply (should never be used when fix works)",
                "created_at": 0,
                "model": "fake",
            }

        with patch.object(main, "resolve_chat_provider", return_value=("http://test", {}, "test-model")), \
             patch.object(httpx, "AsyncClient", FailingClient), \
             patch.object(main, "build_chat_text_reply", side_effect=fake_build_chat_text_reply):
            response = client.post(
                "/api/chat/agent",
                headers={"x-user-id": "test_chat_agent_failure"},
                json={
                    "message": "hello",
                    "provider": "comfly",
                    "model": "gpt-4o-mini",
                },
            )

        # Current (buggy) behavior: 200 + heuristic decision silently substituted.
        # Fixed behavior: 502 because decide_chat_agent_action raises.
        self.assertEqual(
            response.status_code, 502,
            f"Expected 502 from chat-agent LLM failure, got {response.status_code}: {response.text[:200]}",
        )

    def test_runs_workflow_downloads_images_generates_outputs_and_posts_callback(self):
        workflow = {
            "format": "infinite-canvas-workflow",
            "nodes": [
                {"id": "img_1", "type": "image", "url": ""},
                {"id": "group_1", "type": "group", "items": ["img_1"]},
                {"id": "llm_1", "type": "llm", "userInput": "生成两张图", "systemPrompt": "系统提示", "model": "MiniMax-M3", "llmProvider": "custom-api"},
                {"id": "split_1", "type": "json-splitter"},
                {"id": "gen_1", "type": "generator", "apiProvider": "agnes-ai", "model": "agnes-image", "ratio": "square", "resolution": "2k"},
                {"id": "gen_2", "type": "generator", "apiProvider": "agnes-ai", "model": "agnes-image", "ratio": "square", "resolution": "2k"},
                {"id": "out_1", "type": "output"},
            ],
            "connections": [
                {"from": "group_1", "to": "llm_1"},
                {"from": "llm_1", "to": "split_1"},
                {"from": "split_1", "fromPort": 0, "to": "gen_1"},
                {"from": "split_1", "fromPort": 1, "to": "gen_2"},
                {"from": "group_1", "to": "gen_1"},
                {"from": "group_1", "to": "gen_2"},
                {"from": "gen_1", "to": "out_1"},
                {"from": "gen_2", "to": "out_1"},
            ],
        }
        payload = main.AutomationWorkflowRunRequest(
            workflow=workflow,
            image_urls=["https://example.com/product.png"],
            callback_url="https://example.com/callback",
        )
        task_id = "auto_test_run"
        main.AUTOMATION_WORKFLOW_TASKS[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "images": [],
            "error": "",
            "callback_url": payload.callback_url,
            "created_at": 1,
            "updated_at": 1,
            "workflow": workflow,
        }

        llm_output = json.dumps({"prompts": ["第一张 prompt", "第二张 prompt"]}, ensure_ascii=False)
        generated = [
            {"images": ["/assets/output/one.png"]},
            {"images": ["/assets/output/two.png"]},
        ]

        with patch.object(main, "automation_download_input_images", new=AsyncMock(return_value=["/assets/input/product.png"])), \
             patch.object(main, "automation_call_llm_node", new=AsyncMock(return_value=llm_output)), \
             patch.object(main, "build_online_image_result", new=AsyncMock(side_effect=generated)) as image_mock, \
             patch.object(main, "automation_post_callback", new=AsyncMock()) as callback_mock:
            asyncio.run(main.run_automation_workflow_task(task_id, payload))

        task = main.AUTOMATION_WORKFLOW_TASKS[task_id]
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(task["images"], ["/assets/output/one.png", "/assets/output/two.png"])
        self.assertEqual(image_mock.await_count, 2)
        callback_mock.assert_awaited_once()
        callback_payload = callback_mock.await_args.args[1]
        self.assertEqual(callback_payload["task_id"], task_id)
        self.assertEqual(callback_payload["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
