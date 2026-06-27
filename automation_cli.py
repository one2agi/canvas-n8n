import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_SERVER = "http://127.0.0.1:3000"


def normalized_server(value):
    return str(value or DEFAULT_SERVER).rstrip("/")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="automation_cli",
        description="Infinite-Canvas automation workflow CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list-workflows", help="List server-side automation workflow presets")
    list_parser.add_argument("--server", default=DEFAULT_SERVER, help="Infinite-Canvas server URL")

    canvases_parser = sub.add_parser("list-canvases", help="List saved canvases available for automation")
    canvases_parser.add_argument("--server", default=DEFAULT_SERVER, help="Infinite-Canvas server URL")

    run_parser = sub.add_parser("run", help="Run an automation workflow from a preset or saved canvas")
    run_parser.add_argument("--server", default=DEFAULT_SERVER, help="Infinite-Canvas server URL")
    source_group = run_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--workflow", default="", help="Automation workflow preset name")
    source_group.add_argument("--canvas", default="", help="Saved canvas ID")
    run_parser.add_argument("--image-url", action="append", default=[], help="Input image URL; can be repeated")
    run_parser.add_argument("--image-list", default="", help="Text file containing one image URL per line")
    run_parser.add_argument("--callback-url", default="", help="Callback URL to receive the final task payload")
    run_parser.add_argument("--no-wait", action="store_true", help="Return after task submission")
    run_parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval in seconds")
    run_parser.add_argument("--timeout", type=float, default=0, help="Max seconds to wait; 0 means no timeout")
    return parser.parse_args(argv)


def collect_image_urls(args):
    urls = [str(item or "").strip() for item in (getattr(args, "image_url", None) or []) if str(item or "").strip()]
    image_list = str(getattr(args, "image_list", "") or "").strip()
    if image_list:
        with open(image_list, "r", encoding="utf-8-sig") as f:
            urls.extend(line.strip() for line in f if line.strip() and not line.lstrip().startswith("#"))
    return urls


def json_request(method, url, payload=None):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc
    return json.loads(body) if body else {}


def print_json(data, stdout):
    stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def list_workflows_command(args, stdout=sys.stdout):
    server = normalized_server(args.server)
    data = json_request("GET", f"{server}/api/automation/workflows")
    print_json(data, stdout)
    return 0


def list_canvases_command(args, stdout=sys.stdout):
    server = normalized_server(args.server)
    data = json_request("GET", f"{server}/api/automation/canvases")
    print_json(data, stdout)
    return 0


def wait_for_task(server, task_id, interval, timeout, stdout):
    start = time.time()
    while True:
        task = json_request("GET", f"{server}/api/automation/workflow-runs/{urllib.parse.quote(task_id)}")
        status = task.get("status")
        if status in {"succeeded", "failed"}:
            print_json(task, stdout)
            return 0 if status == "succeeded" else 2
        if timeout and time.time() - start > timeout:
            print_json({"task_id": task_id, "status": "timeout", "last_status": status}, stdout)
            return 3
        time.sleep(max(0.2, float(interval or 2.0)))


def run_command(args, stdout=sys.stdout):
    server = normalized_server(args.server)
    image_urls = collect_image_urls(args)
    if not image_urls:
        raise SystemExit("At least one --image-url or --image-list entry is required")
    payload = {
        "image_urls": image_urls,
        "callback_url": args.callback_url,
    }
    if args.canvas:
        payload["canvas_id"] = args.canvas
    else:
        payload["workflow_name"] = args.workflow
    result = json_request("POST", f"{server}/api/automation/workflow-runs", payload)
    if args.no_wait:
        print_json(result, stdout)
        return 0
    task_id = result.get("task_id")
    if not task_id:
        print_json(result, stdout)
        return 1
    return wait_for_task(server, task_id, args.poll_interval, args.timeout, stdout)


def main(argv=None, stdout=sys.stdout, stderr=sys.stderr):
    try:
        args = parse_args(argv)
        if args.command == "list-workflows":
            return list_workflows_command(args, stdout)
        if args.command == "list-canvases":
            return list_canvases_command(args, stdout)
        if args.command == "run":
            return run_command(args, stdout)
        raise SystemExit(f"Unknown command: {args.command}")
    except SystemExit:
        raise
    except Exception as exc:
        stderr.write(f"Error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
