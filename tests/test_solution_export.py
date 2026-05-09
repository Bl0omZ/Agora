"""Tests for POST /api/solution/export."""

from fastapi.testclient import TestClient

from src import web_server

client = TestClient(web_server.app)


def test_solution_export_generates_markdown():
    """方案导出返回包含主题、参与方和结论的 Markdown."""
    payload = {
        "topic": "测试讨论",
        "distilled_conclusion": "提炼结论。",
        "voting_conclusion": "多数赞成。",
        "participants": [
            {"name": "Host", "model": "mimo/mimo-v2.5-pro", "role": "主持人"},
            {"name": "Architect", "model": "ant/GLM-5.1", "role": "架构师"},
        ],
        "votes": [
            {"agent_name": "Architect", "stance": "赞成", "confidence": 0.9, "reason": "可行"},
        ],
    }
    resp = client.post("/api/solution/export", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["filename"].endswith(".md")
    assert "测试讨论" in data["content"]
    assert "Synthesizer" in data["content"]
    assert "Host" in data["content"]
    assert "mimo/mimo-v2.5-pro" in data["content"]
    assert "提炼结论" in data["content"]
    assert "多数赞成" in data["content"]
    assert "赞成" in data["content"]


def test_solution_export_minimal_payload():
    """最简 payload 不报错."""
    resp = client.post("/api/solution/export", json={"topic": "最简"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "最简" in data["content"]


def test_solution_export_topic_sanitized():
    """文件名去掉 unsafe 字符."""
    resp = client.post("/api/solution/export", json={"topic": "测试/讨论:风险?评估"})
    assert resp.status_code == 200
    data = resp.json()
    assert "/" not in data["filename"]
    assert ":" not in data["filename"]