"""Run a real WebSocket E2E discussion against the local web server."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
import uuid
from typing import Any

import websockets


DEFAULT_TOPIC = "作为安全工程师需要发送漏洞工单给研发，需要在安全工单中输出哪些内容可以保证清晰易懂"
DEFAULT_FREEFORM = (
    "偏向输出一份研发能直接执行的漏洞工单内容清单，包含必要字段、复现步骤、风险说明、修复建议和验收标准。"
)


def _preview(text: str, limit: int = 140) -> str:
    return text.replace("\n", " ")[:limit]


def _choose_options(event: dict[str, Any]) -> list[str]:
    options = event.get("options") or []
    if not options:
        return []
    option_count = random.randint(1, min(2, len(options))) if event.get("allow_multiple") else 1
    return [item.get("id") for item in random.sample(options, option_count)]


async def run_e2e(args: argparse.Namespace) -> int:
    started = time.time()
    session_id = f"e2e-{uuid.uuid4()}"
    messages: list[dict[str, Any]] = []
    phases: list[str] = []
    summary = ""
    voting_result: dict[str, Any] | None = None
    answered = 0
    confirmed = 0

    async with websockets.connect(args.url, ping_interval=20, ping_timeout=20, close_timeout=5) as ws:
        await ws.send(json.dumps({
            "action": "start",
            "topic": args.topic,
            "client_session_id": session_id,
        }, ensure_ascii=False))
        print(f"E2E_START session={session_id}")

        while time.time() - started < args.max_seconds:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=args.event_timeout)
            except asyncio.TimeoutError:
                print(f"E2E_TIMEOUT waiting_event elapsed={time.time() - started:.1f}s")
                return 2

            event = json.loads(raw)
            event_type = event.get("type")

            if event_type == "phase":
                phase = event.get("phase")
                phases.append(phase)
                print(f"PHASE {phase}")
            elif event_type == "message":
                content = event.get("content") or ""
                messages.append(event)
                print(
                    "MESSAGE "
                    f"phase={event.get('phase')} name={event.get('name')} "
                    f"len={len(content)} has_think={'<think' in content.lower()} "
                    f"text={_preview(content)}"
                )
            elif event_type == "moderator_question":
                answered += 1
                chosen = _choose_options(event)
                print(f"QUESTION round={event.get('round')} chosen={chosen}")
                await ws.send(json.dumps({
                    "action": "moderator_answer",
                    "client_session_id": session_id,
                    "question_id": event.get("id"),
                    "selected_option_ids": chosen,
                    "freeform_text": args.freeform,
                }, ensure_ascii=False))
            elif event_type == "topic_refined":
                confirmed += 1
                print(f"TOPIC_REFINED {_preview(event.get('refined_topic') or '')}")
                await ws.send(json.dumps({
                    "action": "topic_confirmed",
                    "client_session_id": session_id,
                    "accept": True,
                }, ensure_ascii=False))
            elif event_type == "agent_status":
                print(f"AGENT_STATUS {event.get('name')} {event.get('status')}")
            elif event_type == "summary":
                summary = event.get("content") or ""
                print(f"SUMMARY len={len(summary)} text={_preview(summary)}")
            elif event_type == "voting_result":
                voting_result = event
                print(
                    "VOTING "
                    f"votes={len(event.get('votes') or [])} "
                    f"conclusion={event.get('conclusion')}"
                )
            elif event_type == "ready":
                final_messages = [msg for msg in messages if msg.get("phase") in ("discussion", "synthesis")]
                has_think = any("<think" in (msg.get("content") or "").lower() for msg in messages)
                print(
                    "E2E_READY "
                    f"elapsed={time.time() - started:.1f}s answered={answered} confirmed={confirmed} "
                    f"phases={','.join(phases)} messages={len(messages)} "
                    f"final_msgs={len(final_messages)} has_summary={bool(summary)} "
                    f"has_votes={bool(voting_result)} has_think={has_think}"
                )
                if final_messages and summary and voting_result and not has_think:
                    return 0
                return 3
            elif event_type == "error":
                print(f"E2E_ERROR {event.get('message')!r}")
                return 4
            else:
                print(f"EVENT {event_type}")

    print("E2E_TIMEOUT total")
    return 5


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a real agent-discussion WebSocket E2E scenario.")
    parser.add_argument("--url", default="ws://localhost:8001/ws")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--freeform", default=DEFAULT_FREEFORM)
    parser.add_argument("--max-seconds", type=int, default=900)
    parser.add_argument("--event-timeout", type=int, default=150)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    raise SystemExit(asyncio.run(run_e2e(args)))


if __name__ == "__main__":
    main()
