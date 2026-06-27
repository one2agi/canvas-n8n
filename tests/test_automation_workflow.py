import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import main


class AutomationWorkflowTests(unittest.TestCase):
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
