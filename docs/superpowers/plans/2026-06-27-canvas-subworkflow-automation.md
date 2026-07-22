# Canvas Subworkflow Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add API and CLI support for listing and running a selected detected subworkflow inside a saved canvas, with support for remote image URLs and local image uploads.

**Architecture:** Mirror the browser's detected-workflow graph algorithm in backend Python so API and UI agree on `workflow_1`, `workflow_2`, etc. Keep the existing automation runner and add a resolver step that slices a saved canvas down to the selected subworkflow before execution. Extend the CLI as a thin client that can list canvas subworkflows, upload local image files, and submit the selected run.

**Tech Stack:** FastAPI, Pydantic, Python standard library `urllib`, existing `automation_cli.py`, existing `unittest` tests with FastAPI `TestClient`.

---

## File Structure

- Modify `D:\project\canvas\Infinite-Canvas\main.py`
  - Add `canvas_workflow_id` to `AutomationWorkflowRunRequest`.
  - Add backend detected-workflow helper functions near existing automation helpers.
  - Add `GET /api/automation/canvases/{canvas_id}/workflows`.
  - Add `POST /api/automation/upload`.
  - Extend workflow resolution to slice a saved canvas by subworkflow ID.
  - Extend input image preparation to accept internal `/assets/...` URLs.
- Modify `D:\project\canvas\Infinite-Canvas\automation_cli.py`
  - Add `list-canvas-workflows`.
  - Add `--canvas-workflow`.
  - Add `--image-file`.
  - Add multipart upload support using the Python standard library.
- Modify `D:\project\canvas\Infinite-Canvas\tests\test_automation_workflow.py`
  - Add backend tests for detection, listing, selected-run resolution, upload, and internal asset input handling.
- Modify `D:\project\canvas\Infinite-Canvas\tests\test_automation_cli.py`
  - Add CLI tests for list-canvas-workflows, selected workflow run payload, and local file upload.

---

### Task 1: Add Backend Tests for Canvas Subworkflow Detection

**Files:**
- Modify: `D:\project\canvas\Infinite-Canvas\tests\test_automation_workflow.py`
- Test: `D:\project\canvas\Infinite-Canvas\tests\test_automation_workflow.py`

- [ ] **Step 1: Add a reusable two-workflow fixture test**

Add these tests inside `AutomationWorkflowTests`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail for missing functions**

Run:

```bash
.\python\python.exe -m pytest tests/test_automation_workflow.py::AutomationWorkflowTests::test_detects_canvas_subworkflows_like_frontend tests/test_automation_workflow.py::AutomationWorkflowTests::test_canvas_subworkflow_payload_contains_only_selected_component -v
```

Expected: FAIL with `AttributeError` for `automation_detect_canvas_workflows` or `automation_canvas_subworkflow_payload`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_automation_workflow.py
git commit -m "test: cover canvas subworkflow detection"
```

---

### Task 2: Implement Backend Detected-Workflow Helpers

**Files:**
- Modify: `D:\project\canvas\Infinite-Canvas\main.py`
- Test: `D:\project\canvas\Infinite-Canvas\tests\test_automation_workflow.py`

- [ ] **Step 1: Add constants and sorting helpers near existing automation constants**

In `main.py`, near `AUTOMATION_RUN_TYPES`, add:

```python
AUTOMATION_DETECTED_RUN_TYPES = {
    "llm", "json-splitter", "json-extractor", "generator",
    "msgen", "comfy", "ltxDirector", "video", "rh",
}

def automation_detected_node_sort_key(node):
    item = node or {}
    return (
        float(item.get("x") or 0),
        float(item.get("y") or 0),
        str(item.get("id") or ""),
    )

def automation_workflow_bounds_for_nodes(nodes):
    if not nodes:
        return {"x": 0, "y": 0, "w": 0, "h": 0}
    rects = []
    for node in nodes:
        x = float(node.get("x") or 0)
        y = float(node.get("y") or 0)
        w = float(node.get("w") or 260)
        h = float(node.get("h") or 200)
        rects.append((x, y, x + w, y + h))
    min_x = min(item[0] for item in rects)
    min_y = min(item[1] for item in rects)
    max_x = max(item[2] for item in rects)
    max_y = max(item[3] for item in rects)
    return {"x": min_x, "y": min_y, "w": max_x - min_x, "h": max_y - min_y}
```

- [ ] **Step 2: Add graph order helpers**

Add below `automation_output_connection_ids`:

```python
def automation_is_detected_runnable_node(node):
    return (node or {}).get("type") in AUTOMATION_DETECTED_RUN_TYPES

def automation_compute_detected_run_graph(workflow, detected):
    nodes = workflow.get("nodes") or []
    connections = workflow.get("connections") or []
    node_by_id = automation_node_map(workflow)
    workflow_node_ids = {str(item) for item in detected.get("node_ids") or []}
    runnable_ids = [
        str(item)
        for item in detected.get("runnable_ids") or []
        if str(item) in workflow_node_ids and automation_is_detected_runnable_node(node_by_id.get(str(item)))
    ]
    runnable_set = set(runnable_ids)
    edges = {node_id: set() for node_id in runnable_ids}
    indegree = {node_id: 0 for node_id in runnable_ids}
    incoming_port_rank = {}
    outgoing = {}
    for conn in connections:
        from_id = str(conn.get("from") or "")
        to_id = str(conn.get("to") or "")
        if from_id not in workflow_node_ids or to_id not in workflow_node_ids:
            continue
        outgoing.setdefault(from_id, []).append(to_id)
        from_node = node_by_id.get(from_id)
        if (from_node or {}).get("type") in {"json-splitter", "json-extractor"} and to_id in runnable_set:
            try:
                port = float(conn.get("fromPort"))
            except Exception:
                port = math.inf
            incoming_port_rank[to_id] = min(incoming_port_rank.get(to_id, math.inf), port)

    def add_edge(from_id, to_id):
        if from_id == to_id or from_id not in runnable_set or to_id not in runnable_set:
            return
        if to_id in edges[from_id]:
            return
        edges[from_id].add(to_id)
        indegree[to_id] = indegree.get(to_id, 0) + 1

    for from_id in runnable_ids:
        queue = list(outgoing.get(from_id) or [])
        seen = set()
        while queue:
            next_id = str(queue.pop(0) or "")
            if next_id in seen or next_id not in workflow_node_ids:
                continue
            seen.add(next_id)
            if next_id in runnable_set:
                add_edge(from_id, next_id)
                continue
            queue.extend(outgoing.get(next_id) or [])

    def sort_key(node_id):
        port = incoming_port_rank.get(node_id, math.inf)
        port_key = port if math.isfinite(port) else math.inf
        return (port_key, *automation_detected_node_sort_key(node_by_id.get(node_id) or {"id": node_id}))

    return {
        "runnable_ids": runnable_ids,
        "edges": edges,
        "indegree": indegree,
        "sort_key": sort_key,
    }

def automation_compute_detected_run_order(workflow, detected):
    graph = automation_compute_detected_run_graph(workflow, detected)
    runnable_ids = graph["runnable_ids"]
    indegree = dict(graph["indegree"])
    ready = sorted([node_id for node_id in runnable_ids if indegree.get(node_id, 0) == 0], key=graph["sort_key"])
    order = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for to_id in sorted(graph["edges"].get(node_id) or [], key=graph["sort_key"]):
            indegree[to_id] = indegree.get(to_id, 0) - 1
            if indegree.get(to_id) == 0:
                ready.append(to_id)
        ready.sort(key=graph["sort_key"])
    missing = sorted([node_id for node_id in runnable_ids if node_id not in order], key=graph["sort_key"])
    order.extend(missing)
    return order
```

- [ ] **Step 3: Add detection and slicing helpers**

Add below the graph helpers:

```python
def automation_detect_canvas_workflows(workflow):
    nodes = [node for node in (workflow.get("nodes") or []) if isinstance(node, dict)]
    connections = [conn for conn in (workflow.get("connections") or []) if isinstance(conn, dict)]
    node_by_id = {str(node.get("id") or ""): node for node in nodes if node.get("id")}
    adjacency = {node_id: set() for node_id in node_by_id}
    for conn in connections:
        from_id = str(conn.get("from") or "")
        to_id = str(conn.get("to") or "")
        if from_id not in node_by_id or to_id not in node_by_id:
            continue
        adjacency[from_id].add(to_id)
        adjacency[to_id].add(from_id)
    for node in nodes:
        node_id = str(node.get("id") or "")
        for item_id in node.get("items") or []:
            item_id = str(item_id or "")
            if node_id not in node_by_id or item_id not in node_by_id:
                continue
            adjacency[node_id].add(item_id)
            adjacency[item_id].add(node_id)

    visited = set()
    groups = []
    for start in sorted(nodes, key=automation_detected_node_sort_key):
        start_id = str(start.get("id") or "")
        if not start_id or start_id in visited:
            continue
        queue = [start_id]
        ids = []
        visited.add(start_id)
        while queue:
            node_id = queue.pop(0)
            ids.append(node_id)
            for next_id in sorted(adjacency.get(node_id) or []):
                if next_id in visited:
                    continue
                visited.add(next_id)
                queue.append(next_id)
        group_nodes = sorted([node_by_id[node_id] for node_id in ids if node_id in node_by_id], key=automation_detected_node_sort_key)
        runnable_ids = [str(node.get("id") or "") for node in group_nodes if automation_is_detected_runnable_node(node)]
        if not runnable_ids:
            continue
        id_set = {str(node.get("id") or "") for node in group_nodes}
        group_connections = [
            conn for conn in connections
            if str(conn.get("from") or "") in id_set and str(conn.get("to") or "") in id_set
        ]
        bounds = automation_workflow_bounds_for_nodes(group_nodes)
        groups.append({
            "node_ids": [str(node.get("id") or "") for node in group_nodes],
            "runnable_ids": runnable_ids,
            "connection_ids": [str(conn.get("id") or "") for conn in group_connections if conn.get("id")],
            "node_count": len(group_nodes),
            "connection_count": len(group_connections),
            "bounds": bounds,
            "sort_x": bounds["x"],
            "sort_y": bounds["y"],
        })

    groups.sort(key=lambda item: (item["sort_x"], item["sort_y"]))
    output_ids = {str(node.get("id") or "") for node in nodes if node.get("type") == "output"}
    image_node_ids = {str(node.get("id") or "") for node in nodes if node.get("type") == "image"}
    result = []
    for index, item in enumerate(groups, start=1):
        workflow_id = f"workflow_{index}"
        node_id_set = set(item["node_ids"])
        run_order = automation_compute_detected_run_order(workflow, item)
        input_image_count = len(image_node_ids.intersection(node_id_set))
        output_node_count = len(output_ids.intersection(node_id_set))
        result.append({
            "workflow_id": workflow_id,
            "id": workflow_id,
            "label": f"工作流 {index} · {item['node_count']} 节点 · {item['connection_count']} 连线",
            "node_ids": item["node_ids"],
            "runnable_ids": item["runnable_ids"],
            "connection_ids": item["connection_ids"],
            "node_count": item["node_count"],
            "connection_count": item["connection_count"],
            "bounds": item["bounds"],
            "run_order": run_order,
            "input_image_count": input_image_count,
            "output_node_count": output_node_count,
        })
    return result

def automation_canvas_subworkflow_payload(workflow, canvas_workflow_id):
    workflow_id = str(canvas_workflow_id or "").strip()
    detected = automation_detect_canvas_workflows(workflow)
    match = next((item for item in detected if item.get("workflow_id") == workflow_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"画布子工作流不存在：{workflow_id}")
    node_ids = set(match.get("node_ids") or [])
    connection_ids = set(match.get("connection_ids") or [])
    nodes = [copy.deepcopy(node) for node in (workflow.get("nodes") or []) if str(node.get("id") or "") in node_ids]
    connections = [
        copy.deepcopy(conn)
        for conn in (workflow.get("connections") or [])
        if (str(conn.get("id") or "") in connection_ids)
        or (str(conn.get("from") or "") in node_ids and str(conn.get("to") or "") in node_ids)
    ]
    return {
        "format": "infinite-canvas-workflow",
        "nodes": nodes,
        "connections": connections,
        "canvas_workflow_id": workflow_id,
    }
```

- [ ] **Step 4: Run detection tests**

Run:

```bash
.\python\python.exe -m pytest tests/test_automation_workflow.py::AutomationWorkflowTests::test_detects_canvas_subworkflows_like_frontend tests/test_automation_workflow.py::AutomationWorkflowTests::test_canvas_subworkflow_payload_contains_only_selected_component -v
```

Expected: PASS.

- [ ] **Step 5: Commit implementation**

```bash
git add main.py tests/test_automation_workflow.py
git commit -m "feat: detect canvas subworkflows on backend"
```

---

### Task 3: Add API Endpoint and Run Request Field

**Files:**
- Modify: `D:\project\canvas\Infinite-Canvas\main.py`
- Modify: `D:\project\canvas\Infinite-Canvas\tests\test_automation_workflow.py`
- Test: `D:\project\canvas\Infinite-Canvas\tests\test_automation_workflow.py`

- [ ] **Step 1: Add API tests**

Add to `AutomationWorkflowTests`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.\python\python.exe -m pytest tests/test_automation_workflow.py::AutomationWorkflowTests::test_lists_canvas_subworkflows_api tests/test_automation_workflow.py::AutomationWorkflowTests::test_create_workflow_run_loads_selected_canvas_subworkflow -v
```

Expected: FAIL because route and request field do not exist.

- [ ] **Step 3: Extend request model**

In `AutomationWorkflowRunRequest`, add:

```python
    canvas_workflow_id: str = ""
```

- [ ] **Step 4: Add canvas workflow listing helper and route**

Near `automation_canvas_records`, add:

```python
def automation_canvas_workflow_records(canvas_id):
    canvas = load_canvas(canvas_id)
    workflow = automation_workflow_from_canvas(canvas_id)
    return {
        "canvas_id": canvas.get("id") or canvas_id,
        "title": canvas.get("title", "未命名画布"),
        "workflows": automation_detect_canvas_workflows(workflow),
    }
```

Near existing automation routes, add:

```python
@app.get("/api/automation/canvases/{canvas_id}/workflows")
async def list_automation_canvas_workflows(canvas_id: str):
    return automation_canvas_workflow_records(canvas_id)
```

- [ ] **Step 5: Extend canvas workflow resolution**

Replace `automation_workflow_from_canvas` with:

```python
def automation_workflow_from_canvas(canvas_id, canvas_workflow_id=""):
    canvas = load_canvas(canvas_id)
    nodes = canvas.get("nodes") or []
    connections = canvas.get("connections") or []
    if not isinstance(nodes, list) or not isinstance(connections, list):
        raise HTTPException(status_code=400, detail="画布格式不正确，缺少 nodes/connections")
    workflow = {
        "format": "infinite-canvas-workflow",
        "nodes": nodes,
        "connections": connections,
    }
    if str(canvas_workflow_id or "").strip():
        return automation_canvas_subworkflow_payload(workflow, canvas_workflow_id)
    return workflow
```

Update `automation_resolve_workflow`:

```python
    if payload.canvas_id:
        return automation_workflow_from_canvas(payload.canvas_id, payload.canvas_workflow_id)
```

Update `automation_workflow_source` to keep returning `"canvas"` for canvas runs.

- [ ] **Step 6: Store canvas workflow metadata on tasks**

In `create_automation_workflow_run`, add the new field in the task dict:

```python
            "canvas_workflow_id": payload.canvas_workflow_id,
```

- [ ] **Step 7: Run API tests**

Run:

```bash
.\python\python.exe -m pytest tests/test_automation_workflow.py::AutomationWorkflowTests::test_lists_canvas_subworkflows_api tests/test_automation_workflow.py::AutomationWorkflowTests::test_create_workflow_run_loads_selected_canvas_subworkflow -v
```

Expected: PASS.

- [ ] **Step 8: Commit API work**

```bash
git add main.py tests/test_automation_workflow.py
git commit -m "feat: expose selected canvas workflow automation api"
```

---

### Task 4: Add Automation Upload and Internal Asset URL Support

**Files:**
- Modify: `D:\project\canvas\Infinite-Canvas\main.py`
- Modify: `D:\project\canvas\Infinite-Canvas\tests\test_automation_workflow.py`
- Test: `D:\project\canvas\Infinite-Canvas\tests\test_automation_workflow.py`

- [ ] **Step 1: Add upload and internal URL tests**

Add to `AutomationWorkflowTests`:

```python
    def test_automation_upload_saves_input_asset(self):
        client = TestClient(main.app)

        response = client.post(
            "/api/automation/upload",
            files={"file": ("product.png", b"fake-image-bytes", "image/png")},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["url"].startswith("/assets/input/automation_"))
        self.assertEqual(body["name"], "product.png")

    def test_prepare_input_images_accepts_internal_asset_url(self):
        result = asyncio.run(main.automation_prepare_input_images(["/assets/input/product.png"]))

        self.assertEqual(result, ["/assets/input/product.png"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.\python\python.exe -m pytest tests/test_automation_workflow.py::AutomationWorkflowTests::test_automation_upload_saves_input_asset tests/test_automation_workflow.py::AutomationWorkflowTests::test_prepare_input_images_accepts_internal_asset_url -v
```

Expected: FAIL because route and `automation_prepare_input_images` do not exist.

- [ ] **Step 3: Add safe internal URL helper**

Near `automation_image_name_from_url`, add:

```python
def automation_is_internal_asset_url(url):
    value = str(url or "").strip()
    return value.startswith("/assets/input/") or value.startswith("/assets/output/") or value.startswith("/output/")

def automation_validate_internal_asset_url(url):
    value = str(url or "").strip()
    if not automation_is_internal_asset_url(value):
        raise HTTPException(status_code=400, detail=f"图片 URL 只支持 http/https 或内部资源路径：{value}")
    if ".." in value.replace("\\", "/").split("/"):
        raise HTTPException(status_code=400, detail=f"内部资源路径不合法：{value}")
    return value
```

- [ ] **Step 4: Replace input image preparation**

Rename existing `automation_download_input_images` to `automation_prepare_input_images` and update its body:

```python
async def automation_prepare_input_images(image_urls):
    prepared = []
    remote_urls = []
    remote_indexes = []
    for index, image_url in enumerate(image_urls or []):
        url = str(image_url or "").strip()
        if not url:
            continue
        if url.startswith(("http://", "https://")):
            remote_indexes.append(index)
            remote_urls.append(url)
            prepared.append("")
        elif automation_is_internal_asset_url(url):
            prepared.append(automation_validate_internal_asset_url(url))
        else:
            raise HTTPException(status_code=400, detail=f"图片 URL 只支持 http/https 或内部资源路径：{url}")

    os.makedirs(OUTPUT_INPUT_DIR, exist_ok=True)
    timeout = httpx.Timeout(connect=20.0, read=120.0, write=30.0, pool=20.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for prepared_index, remote_url in zip(remote_indexes, remote_urls):
            response = await client.get(remote_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            ext = mimetypes.guess_extension(content_type) or os.path.splitext(urllib.parse.urlparse(remote_url).path)[1] or ".png"
            if ext == ".jpe":
                ext = ".jpg"
            filename = f"automation_{int(time.time())}_{uuid.uuid4().hex[:8]}_{prepared_index}{ext}"
            target = os.path.join(OUTPUT_INPUT_DIR, filename)
            with open(target, "wb") as f:
                f.write(response.content)
            prepared[prepared_index] = f"/assets/input/{filename}"
    return prepared
```

Update `run_automation_workflow_task`:

```python
        local_images = await automation_prepare_input_images(payload.image_urls)
```

- [ ] **Step 5: Add upload route**

Near automation routes, add:

```python
@app.post("/api/automation/upload")
async def upload_automation_input(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    original_name = file.filename or "automation-input.png"
    ext = os.path.splitext(original_name)[1] or mimetypes.guess_extension(file.content_type or "") or ".png"
    if ext == ".jpe":
        ext = ".jpg"
    filename = f"automation_{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
    os.makedirs(OUTPUT_INPUT_DIR, exist_ok=True)
    target = os.path.join(OUTPUT_INPUT_DIR, filename)
    with open(target, "wb") as f:
        f.write(content)
    return {
        "url": f"/assets/input/{filename}",
        "name": original_name,
        "size": len(content),
    }
```

- [ ] **Step 6: Run upload tests**

Run:

```bash
.\python\python.exe -m pytest tests/test_automation_workflow.py::AutomationWorkflowTests::test_automation_upload_saves_input_asset tests/test_automation_workflow.py::AutomationWorkflowTests::test_prepare_input_images_accepts_internal_asset_url -v
```

Expected: PASS.

- [ ] **Step 7: Commit upload support**

```bash
git add main.py tests/test_automation_workflow.py
git commit -m "feat: support automation input uploads"
```

---

### Task 5: Extend CLI for Subworkflows and Local Files

**Files:**
- Modify: `D:\project\canvas\Infinite-Canvas\automation_cli.py`
- Modify: `D:\project\canvas\Infinite-Canvas\tests\test_automation_cli.py`
- Test: `D:\project\canvas\Infinite-Canvas\tests\test_automation_cli.py`

- [ ] **Step 1: Add CLI tests**

Add to `AutomationCliTests`:

```python
    def test_list_canvas_workflows_calls_canvas_workflows_endpoint(self):
        calls = []

        def fake_json_request(method, url, payload=None):
            calls.append((method, url, payload))
            return {"canvas_id": "canvas123", "workflows": [{"workflow_id": "workflow_2"}]}

        out = StringIO()
        args = automation_cli.parse_args([
            "list-canvas-workflows",
            "--server", "http://127.0.0.1:3000",
            "--canvas", "canvas123",
        ])

        with patch.object(automation_cli, "json_request", side_effect=fake_json_request):
            exit_code = automation_cli.list_canvas_workflows_command(args, stdout=out)

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, [("GET", "http://127.0.0.1:3000/api/automation/canvases/canvas123/workflows", None)])
        self.assertIn("workflow_2", out.getvalue())

    def test_run_posts_canvas_workflow_id(self):
        calls = []

        def fake_json_request(method, url, payload=None):
            calls.append((method, url, payload))
            return {"task_id": "auto_123", "status": "queued"}

        out = StringIO()
        args = automation_cli.parse_args([
            "run",
            "--server", "http://127.0.0.1:3000",
            "--canvas", "canvas123",
            "--canvas-workflow", "workflow_2",
            "--image-url", "https://example.com/product.png",
            "--no-wait",
        ])

        with patch.object(automation_cli, "json_request", side_effect=fake_json_request):
            exit_code = automation_cli.run_command(args, stdout=out)

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls[0][2]["canvas_workflow_id"], "workflow_2")

    def test_run_uploads_image_file_before_submit(self):
        calls = []

        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as f:
            f.write(b"fake-image")
            path = f.name
        try:
            def fake_upload_file(server, file_path):
                calls.append(("UPLOAD", server, file_path))
                return "/assets/input/uploaded.png"

            def fake_json_request(method, url, payload=None):
                calls.append((method, url, payload))
                return {"task_id": "auto_123", "status": "queued"}

            out = StringIO()
            args = automation_cli.parse_args([
                "run",
                "--server", "http://127.0.0.1:3000",
                "--canvas", "canvas123",
                "--canvas-workflow", "workflow_2",
                "--image-file", path,
                "--no-wait",
            ])

            with patch.object(automation_cli, "upload_image_file", side_effect=fake_upload_file), \
                 patch.object(automation_cli, "json_request", side_effect=fake_json_request):
                exit_code = automation_cli.run_command(args, stdout=out)

            self.assertEqual(exit_code, 0)
            self.assertEqual(calls[0], ("UPLOAD", "http://127.0.0.1:3000", path))
            self.assertEqual(calls[1][2]["image_urls"], ["/assets/input/uploaded.png"])
        finally:
            os.remove(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.\python\python.exe -m pytest tests/test_automation_cli.py::AutomationCliTests::test_list_canvas_workflows_calls_canvas_workflows_endpoint tests/test_automation_cli.py::AutomationCliTests::test_run_posts_canvas_workflow_id tests/test_automation_cli.py::AutomationCliTests::test_run_uploads_image_file_before_submit -v
```

Expected: FAIL because CLI command and parameters do not exist.

- [ ] **Step 3: Extend argument parser**

In `parse_args`, add:

```python
    canvas_workflows_parser = sub.add_parser("list-canvas-workflows", help="List detected workflows inside a saved canvas")
    canvas_workflows_parser.add_argument("--server", default=DEFAULT_SERVER, help="Infinite-Canvas server URL")
    canvas_workflows_parser.add_argument("--canvas", required=True, help="Saved canvas ID")
```

In `run_parser`, add:

```python
    run_parser.add_argument("--canvas-workflow", default="", help="Detected workflow ID inside the saved canvas, for example workflow_2")
    run_parser.add_argument("--image-file", action="append", default=[], help="Local image file to upload before running; can be repeated")
```

- [ ] **Step 4: Add upload helper**

Add below `json_request`:

```python
def upload_image_file(server, file_path):
    path = str(file_path or "").strip()
    if not path:
        raise RuntimeError("Empty --image-file path")
    boundary = f"----InfiniteCanvasAutomation{int(time.time() * 1000)}"
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        content = f.read()
    body = b"".join([
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"),
        b"Content-Type: application/octet-stream\r\n\r\n",
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ])
    req = urllib.request.Request(
        f"{server}/api/automation/upload",
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Upload failed: {exc.reason}") from exc
    url = result.get("url")
    if not url:
        raise RuntimeError(f"Upload response missing url: {result}")
    return url
```

Also add `import os` at the top of `automation_cli.py`.

- [ ] **Step 5: Add list canvas workflows command**

Add:

```python
def list_canvas_workflows_command(args, stdout=sys.stdout):
    server = normalized_server(args.server)
    canvas_id = urllib.parse.quote(str(args.canvas or ""), safe="")
    data = json_request("GET", f"{server}/api/automation/canvases/{canvas_id}/workflows")
    print_json(data, stdout)
    return 0
```

Update `main`:

```python
        if args.command == "list-canvas-workflows":
            return list_canvas_workflows_command(args, stdout)
```

- [ ] **Step 6: Extend run command payload**

In `run_command`, after `image_urls = collect_image_urls(args)`, add:

```python
    for image_file in getattr(args, "image_file", None) or []:
        image_urls.append(upload_image_file(server, image_file))
```

When building payload, add:

```python
    if getattr(args, "canvas_workflow", ""):
        payload["canvas_workflow_id"] = args.canvas_workflow
```

- [ ] **Step 7: Run CLI tests**

Run:

```bash
.\python\python.exe -m pytest tests/test_automation_cli.py::AutomationCliTests::test_list_canvas_workflows_calls_canvas_workflows_endpoint tests/test_automation_cli.py::AutomationCliTests::test_run_posts_canvas_workflow_id tests/test_automation_cli.py::AutomationCliTests::test_run_uploads_image_file_before_submit -v
```

Expected: PASS.

- [ ] **Step 8: Commit CLI work**

```bash
git add automation_cli.py tests/test_automation_cli.py
git commit -m "feat: add canvas workflow cli automation"
```

---

### Task 6: Run Full Verification

**Files:**
- Test: `D:\project\canvas\Infinite-Canvas\tests\test_automation_workflow.py`
- Test: `D:\project\canvas\Infinite-Canvas\tests\test_automation_cli.py`
- Test: `D:\project\canvas\Infinite-Canvas\tests\test_canvas_detected_workflows.py`

- [ ] **Step 1: Run automation backend tests**

Run:

```bash
.\python\python.exe -m pytest tests/test_automation_workflow.py -v
```

Expected: PASS.

- [ ] **Step 2: Run CLI tests**

Run:

```bash
.\python\python.exe -m pytest tests/test_automation_cli.py -v
```

Expected: PASS.

- [ ] **Step 3: Run frontend workflow detection regression tests**

Run:

```bash
.\python\python.exe -m pytest tests/test_canvas_detected_workflows.py -v
```

Expected: PASS. This confirms backend changes did not require changing the browser detection contract.

- [ ] **Step 4: Smoke test against local server**

Start the server if needed:

```bash
.\run.bat
```

In a separate terminal, list subworkflows for the known `kk` canvas:

```bash
.\automation.bat list-canvas-workflows --canvas 496a2bd8a5a84f7bb6d73604e69a9994
```

Expected: JSON contains `workflow_1` and `workflow_2`.

- [ ] **Step 5: Smoke test local file upload run**

Run with a real local image:

```bash
.\automation.bat run --canvas 496a2bd8a5a84f7bb6d73604e69a9994 --canvas-workflow workflow_2 --image-file D:\project\canvas\Infinite-Canvas\assets\input\ai_ref_0cd850f629d1.png --no-wait
```

Expected: JSON contains `task_id` and `status: queued`. Poll with:

```bash
.\automation.bat run --canvas 496a2bd8a5a84f7bb6d73604e69a9994 --canvas-workflow workflow_2 --image-file D:\project\canvas\Infinite-Canvas\assets\input\ai_ref_0cd850f629d1.png --timeout 600
```

Expected: final JSON contains `status: succeeded` and non-empty `images`, assuming AI provider credentials and model settings are valid.

- [ ] **Step 6: Commit verification-only updates if any files changed**

If verification required test or doc adjustments, inspect:

```bash
git status --short
```

Then stage the exact implementation and test files used by this plan:

```bash
git add main.py automation_cli.py tests/test_automation_workflow.py tests/test_automation_cli.py
git commit -m "test: verify canvas workflow automation"
```

If no files changed, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: covered canvas subworkflow listing, selected run, URL input, local upload input, CLI upload, callback-compatible result metadata, and compatibility with existing whole-canvas runs.
- Red-flag scan: each implementation step names exact files and provides concrete code or commands.
- Type consistency: design and plan consistently use `canvas_workflow_id` in API payloads and task metadata, and `--canvas-workflow` in CLI arguments.
