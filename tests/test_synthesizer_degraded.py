from src.web_server import _degraded_discussion_summary


def test_degraded_summary_truncates_markdown_to_500_chars():
    raw = "标题\n" + ("很长的总结" * 200)

    summary = _degraded_discussion_summary(raw)

    assert summary.degraded is True
    assert summary.degraded_reason == "json_parse_failed"
    assert summary.participants == []
    assert len(summary.distilled_conclusion) <= 500
