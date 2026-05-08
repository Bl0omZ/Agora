from src.voting import VoteResult, _summarize_conclusion


def test_timeout_votes_are_excluded_from_conclusion_counts():
    conclusion = _summarize_conclusion([
        VoteResult(agent_name="A", stance="赞成", reason="ok", confidence=0.8, source="valid"),
        VoteResult(agent_name="B", stance="赞成", reason="ok", confidence=0.7, source="valid"),
        VoteResult(agent_name="C", stance="中立", reason="超时", confidence=0.0, source="timeout"),
    ])

    assert conclusion == "多数赞成（2 赞成 / 0 反对 / 0 中立）"


def test_error_votes_count_and_are_annotated():
    conclusion = _summarize_conclusion([
        VoteResult(agent_name="A", stance="赞成", reason="ok", confidence=0.8, source="valid"),
        VoteResult(agent_name="B", stance="中立", reason="ValueError", confidence=0.0, source="error"),
    ])

    assert conclusion == "多数赞成（1 赞成 / 0 反对 / 1 中立）（其中 1 票模型异常）"


def test_legacy_vote_infers_source_from_confidence():
    valid = VoteResult.model_validate({
        "agent_name": "A",
        "stance": "赞成",
        "reason": "ok",
        "confidence": 0.5,
    })
    timeout = VoteResult.model_validate({
        "agent_name": "B",
        "stance": "中立",
        "reason": "old timeout",
        "confidence": 0.0,
    })

    assert valid.source == "valid"
    assert timeout.source == "timeout"
