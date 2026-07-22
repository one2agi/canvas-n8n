# Canvas Subworkflow Automation Design

## Goal

Allow an external caller to choose one detected subworkflow inside a saved Infinite-Canvas canvas, provide required upstream image inputs, run the chosen flow automatically, and receive generated image results through CLI, polling API, or callback.

For a product manager, this turns a saved canvas from "a visual editing board" into "a callable production line." A platform can upload a product image, choose `workflow_1` or `workflow_2`, click one button or call one API, and get the output images back.

## Current Behavior

The project already has an automation API and CLI:

- `automation.bat list-canvases` lists saved canvases.
- `automation.bat list-workflows` lists preset JSON files in `automation_workflows/`.
- `automation.bat run --canvas <canvas_id> --image-url <url>` runs a whole saved canvas.
- `POST /api/automation/workflow-runs` queues a task and returns `task_id`.
- `GET /api/automation/workflow-runs/{task_id}` returns task status and images.

The gap is that the web UI can detect multiple runnable workflows inside one canvas, but the automation API cannot list or select those subworkflows. The `kk` canvas is the concrete example: it has two detected subworkflows, but CLI can only see the canvas as one unit.

## Product Scope

First version includes:

- List detected subworkflows for a saved canvas.
- Run a selected detected subworkflow by ID, such as `workflow_1` or `workflow_2`.
- Keep existing whole-canvas execution when no subworkflow ID is provided.
- Accept remote image URLs.
- Accept local images through an upload API.
- Let CLI users pass local files directly with `--image-file`; CLI uploads files before starting the run.
- Return generated image URLs in the existing task result shape.
- Include `canvas_workflow_id` in queued task metadata and final responses.

First version does not include:

- Manual subworkflow naming in the UI.
- Text, number, option, or model-parameter input forms.
- Browser UI changes for managing automation calls.
- Persistent production-grade task storage.
- Retry scheduling or queue workers outside the current in-process task model.

## API Design

### List Canvas Subworkflows

Add:

```http
GET /api/automation/canvases/{canvas_id}/workflows
```

Response:

```json
{
  "canvas_id": "496a2bd8a5a84f7bb6d73604e69a9994",
  "title": "kk",
  "workflows": [
    {
      "workflow_id": "workflow_1",
      "label": "工作流 1 · 14 节点 · 15 连线",
      "node_ids": ["generator_a"],
      "connection_ids": ["conn_a"],
      "runnable_ids": ["generator_a"],
      "node_count": 14,
      "connection_count": 15,
      "run_order": ["generator_a"],
      "input_image_count": 1,
      "output_node_count": 1,
      "bounds": {"x": 0, "y": 0, "w": 100, "h": 100}
    }
  ]
}
```

The ID is intentionally simple in version one. Future naming can add fields like `name` and `slug` without breaking `workflow_id`.

### Upload Local Image

Add:

```http
POST /api/automation/upload
Content-Type: multipart/form-data
```

Form field:

- `file`: uploaded image file.

Response:

```json
{
  "url": "/assets/input/automation_1782540000_ab12cd34.png",
  "name": "product.png",
  "size": 123456
}
```

This gives external platforms a simple "send file first, then run workflow" path. The returned `url` is internal to Infinite-Canvas and can be passed as an input image to the run API.

### Run Workflow

Extend existing:

```http
POST /api/automation/workflow-runs
```

New request shape:

```json
{
  "canvas_id": "496a2bd8a5a84f7bb6d73604e69a9994",
  "canvas_workflow_id": "workflow_2",
  "image_urls": [
    "/assets/input/automation_1782540000_ab12cd34.png"
  ],
  "callback_url": "http://127.0.0.1:3000/api/automation/test-callback"
}
```

Compatibility:

- If `canvas_workflow_id` is missing, existing whole-canvas behavior remains.
- If `workflow_name` is used, preset workflow behavior remains.
- If inline `workflow` is used, inline behavior remains.

Task response:

```json
{
  "task_id": "auto_xxx",
  "status": "queued"
}
```

Final result:

```json
{
  "task_id": "auto_xxx",
  "status": "succeeded",
  "images": ["/assets/output/online_a.png"],
  "workflow_source": "canvas",
  "canvas_id": "496a2bd8a5a84f7bb6d73604e69a9994",
  "canvas_workflow_id": "workflow_2",
  "error": ""
}
```

## CLI Design

Add:

```bash
.\automation.bat list-canvas-workflows --canvas 496a2bd8a5a84f7bb6d73604e69a9994
```

Extend:

```bash
.\automation.bat run ^
  --canvas 496a2bd8a5a84f7bb6d73604e69a9994 ^
  --canvas-workflow workflow_2 ^
  --image-url https://example.com/product.png
```

Add local file input:

```bash
.\automation.bat run ^
  --canvas 496a2bd8a5a84f7bb6d73604e69a9994 ^
  --canvas-workflow workflow_2 ^
  --image-file D:\images\product.png
```

CLI behavior:

1. Collect `--image-url`, `--image-list`, and `--image-file` inputs.
2. Upload each local `--image-file` to `/api/automation/upload`.
3. Merge uploaded internal URLs with URL inputs.
4. Submit `/api/automation/workflow-runs`.
5. Wait for task completion unless `--no-wait` is provided.

## Backend Design

The backend should mirror the front-end workflow detection rules in Python:

1. Treat runnable nodes as the same set used by the front end: `llm`, `json-splitter`, `json-extractor`, `generator`, `msgen`, `comfy`, `ltxDirector`, `video`, `rh`.
2. Build connected components using normal connections and group membership.
3. Ignore components with no runnable nodes.
4. Sort components by canvas position and assign stable IDs `workflow_1`, `workflow_2`, etc.
5. Compute runnable order using dependency edges between runnable nodes, passing through non-runnable nodes.
6. Prefer `json-splitter` / `json-extractor` port order for downstream generator ordering.

When a run request includes `canvas_workflow_id`, the backend should resolve the saved canvas, detect subworkflows, find the requested one, and create a smaller workflow payload containing only that subworkflow's nodes and connections. The existing automation runner can then execute that selected workflow.

## Input Image Handling

Current automation downloads only `http://` and `https://` images. The new version should accept:

- Remote URLs: downloaded into `assets/input/`.
- Internal asset URLs: `/assets/input/...`, `/assets/output/...`, `/output/...`; validated so callers cannot escape project directories.
- Uploaded files: stored in `assets/input/` and then passed as internal asset URLs.

For version one, image assignment remains ordered: first image input fills the first upstream image node, second image fills the second upstream image node, and so on.

## Error Handling

Return clear errors for:

- Canvas not found.
- Canvas has no detected subworkflows.
- Requested `canvas_workflow_id` does not exist.
- Selected subworkflow has no executable image generation node.
- No image input was provided.
- Uploaded file is empty.
- Image input URL is not remote and not a valid internal asset URL.
- Upload or remote download fails.

## Testing Strategy

Add focused tests around:

- Python backend detects two subworkflows from a graph equivalent to `kk`.
- API lists canvas subworkflows.
- API resolves `canvas_workflow_id` to only selected nodes and connections.
- Existing whole-canvas behavior still works.
- Upload endpoint saves a file and returns `/assets/input/...`.
- Runner accepts internal `/assets/input/...` URLs without trying to redownload them.
- CLI sends `canvas_workflow_id`.
- CLI uploads `--image-file` before submitting the workflow run.

## Future Extension

Second phase can add friendly names:

```json
{
  "workflow_id": "workflow_2",
  "name": "五图详情生成",
  "slug": "detail-five-images"
}
```

The API can keep accepting `workflow_2` while also supporting `name` or `slug`, so existing integrations remain valid.
