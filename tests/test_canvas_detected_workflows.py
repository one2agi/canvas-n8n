"""Regression tests for canvas workflow auto-detection algorithms.

The UI renders in the browser, but the workflow grouping and run-order rules
are pure graph logic. These tests slice that logic out of canvas.js and run it
under Node so the behavior stays stable.
"""
import json
import os
import subprocess
import unittest


CANVAS_JS = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "static", "js", "canvas.js")
)


def _extract_workflow_algorithm(code: str) -> str:
    start = code.index("const DETECTED_WORKFLOW_RUN_TYPES = new Set([")
    end = code.index("function renderWorkflowRunBar(", start)
    return code[start:end]


def _extract_cascade_layer_runner(code: str) -> str:
    start = code.index("async function runCascadeNodeOnce(")
    end = code.index("// 失败重试：从该节点继续往下游跑", start)
    return code[start:end]


def run_workflow_algorithm(nodes, connections):
    with open(CANVAS_JS, "r", encoding="utf-8") as f:
        code = f.read()
    algo = _extract_workflow_algorithm(code)
    driver = f"""
let nodes = {json.dumps(nodes, ensure_ascii=False)};
let connections = {json.dumps(connections, ensure_ascii=False)};
{algo}
const workflows = detectCanvasWorkflows();
const orders = workflows.map(w => computeWorkflowRunOrder(w));
const plans = typeof computeWorkflowRunPlan === 'function'
    ? workflows.map(w => computeWorkflowRunPlan(w))
    : '__missing_computeWorkflowRunPlan__';
const defaultActiveId = chooseDetectedWorkflowActiveId('', workflows);
process.stdout.write(JSON.stringify({{workflows, orders, plans, defaultActiveId}}));
"""
    result = subprocess.run(
        ["node", "-e", driver],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    if result.returncode != 0:
        return {"error": f"node exited {result.returncode}: {result.stderr[:500]}"}
    return json.loads(result.stdout)


def run_layer_runner_scenario(script_body: str):
    with open(CANVAS_JS, "r", encoding="utf-8") as f:
        code = f.read()
    runner = _extract_cascade_layer_runner(code)
    driver = f"""
let events = [];
let nodes = [
    {{id:'gen_1', type:'generator'}},
    {{id:'gen_2', type:'generator'}},
    {{id:'gen_3', type:'generator'}}
];
let cascadeCtx = {{targetId:'workflow_1', status:'running', abortRequested:false, message:'', controllers:new Set(), currentNodeId:''}};
let resolvers = {{}};
function cascadeTargetIdFromOptions(options={{}}){{ return String(options?.cascadeTargetId || options?.targetId || ''); }}
function cascadeContextFor(targetId){{ return targetId ? cascadeCtx : null; }}
function ensureCascadeActive(targetId){{ if(cascadeCtx.abortRequested) throw new Error('stopped'); return cascadeCtx; }}
function refreshNodes(ids){{ events.push(['refresh', ...(ids || [])]); }}
function isCascadeAbortError(err){{ return Boolean(err?.isCascadeAbort); }}
function clearCascadeNodeState(node){{ if(node){{ node.runStatus = ''; node.runError = ''; node._cascadeFailed = false; }} }}
function requestCascadeStop(targetId, reason=''){{ cascadeCtx.abortRequested = true; events.push(['stop', targetId, reason]); }}
async function runGenerator(id){{
    events.push(['start', id]);
    await new Promise(resolve => {{ resolvers[id] = resolve; }});
    events.push(['finish', id]);
}}
async function runMsGenNode(){{ throw new Error('unexpected'); }}
async function runComfyNode(){{ throw new Error('unexpected'); }}
async function runLTXDirectorNode(){{ throw new Error('unexpected'); }}
async function runLLMNode(){{ throw new Error('unexpected'); }}
async function runJsonExtractorNode(){{ throw new Error('unexpected'); }}
async function runVideoNode(){{ throw new Error('unexpected'); }}
async function runRhNode(){{ throw new Error('unexpected'); }}
{runner}
{script_body}
"""
    result = subprocess.run(
        ["node", "-e", driver],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    if result.returncode != 0:
        return {"error": f"node exited {result.returncode}: {result.stderr[:500]}"}
    return json.loads(result.stdout)


class CanvasDetectedWorkflowTests(unittest.TestCase):
    def test_detects_two_disconnected_workflows_and_ignores_loose_image(self):
        nodes = [
            {"id": "img_a", "type": "image", "x": 0, "y": 0},
            {"id": "llm_a", "type": "llm", "x": 100, "y": 0},
            {"id": "split_a", "type": "json-splitter", "x": 200, "y": 0},
            {"id": "gen_a1", "type": "generator", "x": 300, "y": 0},
            {"id": "gen_a2", "type": "generator", "x": 300, "y": 120},
            {"id": "out_a", "type": "output", "x": 420, "y": 0},
            {"id": "prompt_b", "type": "prompt", "x": 800, "y": 0},
            {"id": "gen_b", "type": "generator", "x": 920, "y": 0},
            {"id": "out_b", "type": "output", "x": 1040, "y": 0},
            {"id": "loose_img", "type": "image", "x": 1200, "y": 0},
        ]
        connections = [
            {"id": "c1", "from": "img_a", "to": "llm_a"},
            {"id": "c2", "from": "llm_a", "to": "split_a"},
            {"id": "c3", "from": "split_a", "fromPort": 0, "to": "gen_a1"},
            {"id": "c4", "from": "split_a", "fromPort": 1, "to": "gen_a2"},
            {"id": "c5", "from": "gen_a1", "to": "out_a"},
            {"id": "c6", "from": "gen_a2", "to": "out_a"},
            {"id": "c7", "from": "prompt_b", "to": "gen_b"},
            {"id": "c8", "from": "gen_b", "to": "out_b"},
        ]

        result = run_workflow_algorithm(nodes, connections)

        self.assertNotIn("error", result, msg=result.get("error"))
        self.assertEqual(len(result["workflows"]), 2)
        self.assertEqual(result["defaultActiveId"], "workflow_1")
        self.assertEqual(result["workflows"][0]["nodeCount"], 6)
        self.assertEqual(result["workflows"][0]["connectionCount"], 6)
        self.assertEqual(result["orders"][0], ["llm_a", "split_a", "gen_a1", "gen_a2"])
        self.assertEqual(
            result["plans"][0]["layers"],
            [["llm_a"], ["split_a"], ["gen_a1", "gen_a2"]],
        )
        self.assertEqual(result["orders"][1], ["gen_b"])
        self.assertEqual(result["plans"][1]["layers"], [["gen_b"]])

    def test_single_unconnected_runnable_node_is_a_workflow(self):
        nodes = [
            {"id": "gen_solo", "type": "generator", "x": 50, "y": 20},
            {"id": "img_solo", "type": "image", "x": 300, "y": 20},
        ]
        result = run_workflow_algorithm(nodes, [])

        self.assertNotIn("error", result, msg=result.get("error"))
        self.assertEqual(len(result["workflows"]), 1)
        self.assertEqual(result["workflows"][0]["nodeIds"], ["gen_solo"])
        self.assertEqual(result["orders"][0], ["gen_solo"])
        self.assertEqual(result["plans"][0]["layers"], [["gen_solo"]])

    def test_connected_group_includes_its_member_image_nodes(self):
        nodes = [
            {"id": "group_1", "type": "group", "x": 0, "y": 0, "items": ["img_1", "img_2"]},
            {"id": "img_1", "type": "image", "x": 20, "y": 40},
            {"id": "img_2", "type": "image", "x": 80, "y": 40},
            {"id": "llm_1", "type": "llm", "x": 180, "y": 0},
        ]
        connections = [{"id": "c1", "from": "group_1", "to": "llm_1"}]

        result = run_workflow_algorithm(nodes, connections)

        self.assertNotIn("error", result, msg=result.get("error"))
        self.assertEqual(result["workflows"][0]["nodeCount"], 4)
        self.assertEqual(
            set(result["workflows"][0]["nodeIds"]),
            {"group_1", "img_1", "img_2", "llm_1"},
        )
        self.assertEqual(result["orders"][0], ["llm_1"])
        self.assertEqual(result["plans"][0]["layers"], [["llm_1"]])

    def test_branch_order_prefers_json_splitter_port_order_over_position(self):
        nodes = [
            {"id": "split_1", "type": "json-splitter", "x": 0, "y": 0},
            {"id": "gen_port_1", "type": "generator", "x": 300, "y": 200},
            {"id": "gen_port_2", "type": "generator", "x": 100, "y": 20},
        ]
        connections = [
            {"id": "c1", "from": "split_1", "fromPort": 1, "to": "gen_port_2"},
            {"id": "c2", "from": "split_1", "fromPort": 0, "to": "gen_port_1"},
        ]

        result = run_workflow_algorithm(nodes, connections)

        self.assertNotIn("error", result, msg=result.get("error"))
        self.assertEqual(result["orders"][0], ["split_1", "gen_port_1", "gen_port_2"])
        self.assertEqual(result["plans"][0]["layers"], [["split_1"], ["gen_port_1", "gen_port_2"]])

    def test_branch_order_preserves_json_splitter_port_order_through_prompt_node(self):
        nodes = [
            {"id": "split_1", "type": "json-splitter", "x": 0, "y": 0},
            {"id": "prompt_1", "type": "prompt", "x": 300, "y": 0},
            {"id": "gen_port_0", "type": "generator", "x": 900, "y": 0},
            {"id": "gen_port_1", "type": "generator", "x": 600, "y": 0},
        ]
        connections = [
            {"id": "c1", "from": "split_1", "fromPort": 0, "to": "prompt_1"},
            {"id": "c2", "from": "prompt_1", "to": "gen_port_0"},
            {"id": "c3", "from": "split_1", "fromPort": 1, "to": "gen_port_1"},
        ]

        result = run_workflow_algorithm(nodes, connections)

        self.assertNotIn("error", result, msg=result.get("error"))
        self.assertEqual(result["orders"][0], ["split_1", "gen_port_0", "gen_port_1"])
        self.assertEqual(result["plans"][0]["layers"], [["split_1"], ["gen_port_0", "gen_port_1"]])

    def test_shared_json_splitter_fans_out_to_five_parallel_generators(self):
        nodes = [
            {"id": "llm_1", "type": "llm", "x": 0, "y": 0},
            {"id": "split_1", "type": "json-splitter", "x": 240, "y": 0},
            {"id": "gen_1", "type": "generator", "x": 520, "y": 0},
            {"id": "gen_2", "type": "generator", "x": 520, "y": 120},
            {"id": "gen_3", "type": "generator", "x": 520, "y": 240},
            {"id": "gen_4", "type": "generator", "x": 520, "y": 360},
            {"id": "gen_5", "type": "generator", "x": 520, "y": 480},
            {"id": "out_1", "type": "output", "x": 820, "y": 200},
        ]
        connections = [
            {"id": "c1", "from": "llm_1", "to": "split_1"},
            {"id": "c2", "from": "split_1", "fromPort": 0, "to": "gen_1"},
            {"id": "c3", "from": "split_1", "fromPort": 1, "to": "gen_2"},
            {"id": "c4", "from": "split_1", "fromPort": 2, "to": "gen_3"},
            {"id": "c5", "from": "split_1", "fromPort": 3, "to": "gen_4"},
            {"id": "c6", "from": "split_1", "fromPort": 4, "to": "gen_5"},
            {"id": "c7", "from": "gen_1", "to": "out_1"},
            {"id": "c8", "from": "gen_2", "to": "out_1"},
            {"id": "c9", "from": "gen_3", "to": "out_1"},
            {"id": "c10", "from": "gen_4", "to": "out_1"},
            {"id": "c11", "from": "gen_5", "to": "out_1"},
        ]

        result = run_workflow_algorithm(nodes, connections)

        self.assertNotIn("error", result, msg=result.get("error"))
        self.assertEqual(result["orders"][0], ["llm_1", "split_1", "gen_1", "gen_2", "gen_3", "gen_4", "gen_5"])
        self.assertEqual(
            result["plans"][0]["layers"],
            [["llm_1"], ["split_1"], ["gen_1", "gen_2", "gen_3", "gen_4", "gen_5"]],
        )

    def test_layer_runner_starts_independent_nodes_before_next_layer(self):
        result = run_layer_runner_scenario(
            """
(async () => {
    const run = runCascadeLayers([['gen_1', 'gen_2'], ['gen_3']], {cascadeTargetId:'workflow_1'});
    await Promise.resolve();
    const afterFirstTick = events.filter(e => e[0] === 'start').map(e => e[1]);
    resolvers.gen_1();
    await Promise.resolve();
    const afterFirstDone = events.filter(e => e[0] === 'start').map(e => e[1]);
    resolvers.gen_2();
    await Promise.resolve();
    await new Promise(resolve => setTimeout(resolve, 0));
    const afterLayerDone = events.filter(e => e[0] === 'start').map(e => e[1]);
    resolvers.gen_3();
    await run;
    process.stdout.write(JSON.stringify({afterFirstTick, afterFirstDone, afterLayerDone, events}));
})().catch(err => {
    process.stderr.write(err.stack || String(err));
    process.exit(1);
});
"""
        )

        self.assertNotIn("error", result, msg=result.get("error"))
        self.assertEqual(result["afterFirstTick"], ["gen_1", "gen_2"])
        self.assertEqual(result["afterFirstDone"], ["gen_1", "gen_2"])
        self.assertEqual(result["afterLayerDone"], ["gen_1", "gen_2", "gen_3"])

    def test_layer_runner_does_not_start_later_layers_after_stop(self):
        result = run_layer_runner_scenario(
            """
runGenerator = async function(id) {
    events.push(['start', id]);
    if(id === 'gen_1') {
        const err = new Error('stopped');
        err.isCascadeAbort = true;
        throw err;
    }
    events.push(['finish', id]);
};
(async () => {
    let stopped = false;
    try {
        await runCascadeLayers([['gen_1'], ['gen_2']], {cascadeTargetId:'workflow_1'});
    } catch(err) {
        stopped = Boolean(err.isCascadeAbort);
    }
    process.stdout.write(JSON.stringify({stopped, events}));
})().catch(err => {
    process.stderr.write(err.stack || String(err));
    process.exit(1);
});
"""
        )

        self.assertNotIn("error", result, msg=result.get("error"))
        self.assertTrue(result["stopped"])
        self.assertEqual(
            [event[1] for event in result["events"] if event[0] == "start"],
            ["gen_1"],
        )


if __name__ == "__main__":
    unittest.main()
