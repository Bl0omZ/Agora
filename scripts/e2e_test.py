"""E2E WebSocket test: brainstorm (auto-select) → discussion → voting → save."""

import asyncio
import json
import sys
import time
from pathlib import Path

import websockets

WS_URL = "ws://localhost:8001/ws"
TEST_TOPIC = "作为安全工程师需要发送漏洞工单给研发，需要在安全工单中输出哪些内容可以保证清晰易懂，最终给我一份可以被 agent 使用的 prompt"


async def main() -> None:
    print(f"=== E2E TEST ===")
    print(f"Topic: {TEST_TOPIC}")
    print()

    t0 = time.time()
    messages = []
    phase = "connecting"

    async with websockets.connect(WS_URL, max_size=10 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"action": "start", "topic": TEST_TOPIC}))

        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=300)
            except asyncio.TimeoutError:
                print(f"[TIMEOUT] No message for 300s in phase={phase}")
                break

            data = json.loads(raw)
            event_type = data.get("type", "")

            if event_type == "phase":
                phase = data.get("phase", "")
                label = data.get("label", "")
                print(f"\n{'='*60}")
                print(f"  PHASE: {phase} ({label})")
                print(f"{'='*60}")

            elif event_type == "message":
                name = data.get("name", "Unknown")
                content = data.get("content", "")[:300]
                msg_phase = data.get("phase", "")
                print(f"\n  [{name}] ({msg_phase})")
                print(f"  {content}{'...' if len(data.get('content','')) > 300 else ''}")
                messages.append(data)

            elif event_type == "moderator_question":
                question = data.get("question", "")
                options = data.get("options", [])
                print(f"\n  [BRAINSTORM Q] {question}")
                for opt in options:
                    print(f"    - {opt.get('id')}: {opt.get('label')}")

                if options:
                    selected = options[0]
                    print(f"  [AUTO-SELECT] {selected.get('label')}")
                    await ws.send(json.dumps({
                        "action": "moderator_answer",
                        "answer": selected.get("label", ""),
                        "selected_option_ids": [selected.get("id", "")],
                    }))
                else:
                    print(f"  [AUTO-ANSWER] 请全面分析")
                    await ws.send(json.dumps({
                        "action": "moderator_answer",
                        "answer": "请全面分析，涵盖漏洞描述、复现步骤、影响范围、修复建议等关键要素",
                    }))

            elif event_type == "topic_refined":
                refined = data.get("refined_topic", "")
                print(f"\n  [TOPIC REFINED] {refined}")
                print(f"  [AUTO-CONFIRM]")
                await ws.send(json.dumps({"action": "topic_confirmed"}))

            elif event_type == "voting_result":
                votes = data.get("votes", [])
                conclusion = data.get("conclusion", "")
                print(f"\n  === VOTING RESULT ===")
                for v in votes:
                    print(f"    {v['agent_name']}: {v['stance']} (confidence={v.get('confidence', 0):.1f})")
                    print(f"      {v.get('reason', '')[:150]}")
                print(f"  Conclusion: {conclusion}")

            elif event_type == "summary":
                content = data.get("content", "")[:500]
                print(f"\n  === SUMMARY ===")
                print(f"  {content}...")

            elif event_type == "ready":
                print(f"\n  [READY] Pipeline complete, saving report...")
                await ws.send(json.dumps({
                    "action": "save",
                    "topic": TEST_TOPIC,
                }))

            elif event_type == "saved":
                path = data.get("path", "")
                elapsed = time.time() - t0
                print(f"\n  [SAVED] {path}")
                print(f"\n=== E2E TEST DONE in {elapsed:.1f}s ===")
                print(f"Messages: {len(messages)}")
                break

            elif event_type == "error":
                print(f"\n  [ERROR] {data.get('message', '')}")
                break

            elif event_type == "brainstorm_timeout":
                print(f"\n  [BRAINSTORM TIMEOUT]")

            elif event_type in ("started", "agents", "agent_meta", "agent_status"):
                pass
            else:
                print(f"\n  [EVENT] {event_type}: {json.dumps(data, ensure_ascii=False)[:200]}")

    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
