"""Run a real API -> Celery -> PostgreSQL -> Qdrant smoke test against local services."""

import os
import time
from pathlib import Path

import httpx

API = os.getenv("STUDYRAG_E2E_API", "http://127.0.0.1:8000/api/v1")
API_KEY = os.getenv("STUDYRAG_E2E_API_KEY")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}


def request(client: httpx.Client, method: str, path: str, **kwargs: object) -> httpx.Response:
    response = client.request(method, f"{API}{path}", **kwargs)
    response.raise_for_status()
    return response


def wait_for_task(client: httpx.Client, knowledge_base_id: str, task_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        tasks = request(client, "GET", f"/knowledge-bases/{knowledge_base_id}/tasks").json()
        task = next(item for item in tasks if item["id"] == task_id)
        if task["status"] in {"completed", "failed", "cancelled", "partially_completed"}:
            if task["status"] != "completed":
                raise RuntimeError(f"task failed: {task}")
            return task
        time.sleep(1)
    raise TimeoutError(f"task {task_id} did not finish")


def main() -> None:
    with httpx.Client(headers=HEADERS, timeout=30) as client:
        request(client, "GET", "/health/ready")
        knowledge_base = request(
            client,
            "POST",
            "/knowledge-bases",
            json={"name": "ZhiWeave E2E 临时库", "description": "自动化全链路验收"},
        ).json()
        knowledge_base_id = knowledge_base["id"]
        source = Path("/tmp/zhiweave-e2e.md")
        source.write_text(
            "# 混合检索\n\nZhiWeave 同时支持向量语义检索、BM25 关键词检索与 RRF 融合。",
            encoding="utf-8",
        )
        try:
            with source.open("rb") as uploaded:
                task = request(
                    client,
                    "POST",
                    f"/knowledge-bases/{knowledge_base_id}/imports/files",
                    files={"file": (source.name, uploaded, "text/markdown")},
                ).json()
            wait_for_task(client, knowledge_base_id, task["id"])
            for mode in ("semantic", "keyword", "hybrid"):
                hits = request(
                    client,
                    "POST",
                    f"/knowledge-bases/{knowledge_base_id}/search",
                    json={"query": "RRF 混合检索是什么", "mode": mode, "top_k": 3},
                ).json()
                assert hits, f"{mode} search returned no hits"
            report = request(
                client, "GET", f"/knowledge-bases/{knowledge_base_id}/consistency"
            ).json()
            assert report["consistent"], report
            exported = request(
                client, "GET", f"/knowledge-bases/{knowledge_base_id}/export"
            ).content
            assert exported.startswith(b"PK")
        finally:
            request(client, "DELETE", f"/knowledge-bases/{knowledge_base_id}")
            source.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
