"""Non-interactive baseline test: run discussion + voting, save output for comparison."""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.loader import load_config, create_agent, create_service
from src.discussion import build_discussion_transcript, run_discussion
from src.voting import run_voting
from semantic_kernel.contents import AuthorRole, ChatMessageContent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("baseline_test")

TEST_TOPIC = "我们团队的核心Java后端服务（日均请求量500万）需要从单体架构迁移到微服务。当前痛点：部署耗时40分钟、单次发布影响全局、数据库连接池经常打满。请讨论第一阶段应该怎么拆，优先拆哪个模块，用什么技术栈。"


async def main() -> None:
    config_name = sys.argv[1] if len(sys.argv) > 1 else "agents.yaml"
    config_path = str(Path(__file__).resolve().parent.parent / "src" / "config" / config_name)
    config = load_config(config_path)

    manager_config = config.agents[config.manager_service_index]
    discussion_agents = []
    final_agents = []
    for i, ac in enumerate(config.agents):
        if i == config.manager_service_index:
            continue
        agent = create_agent(ac)
        if ac.final_only:
            final_agents.append((ac, agent))
        else:
            discussion_agents.append(agent)

    manager_service = create_service(manager_config)

    messages: list[dict] = []

    def on_message(msg: ChatMessageContent) -> None:
        entry = {"name": msg.name or "Unknown", "role": str(msg.role), "content": msg.content or ""}
        messages.append(entry)
        print(f"\n--- [{msg.name}] ---")
        print(msg.content[:500] if msg.content else "(empty)")
        print()

    print(f"=== BASELINE TEST ===")
    print(f"Topic: {TEST_TOPIC}")
    print(f"Agents: {[ac.name for ac in config.agents]}")
    print(f"Max rounds: {config.discussion.max_rounds}")
    print()

    t0 = time.time()

    summary, history = await run_discussion(
        agents=discussion_agents,
        topic=TEST_TOPIC,
        manager_service=manager_service,
        manager_name=manager_config.name,
        manager_instructions=manager_config.instructions,
        max_rounds=config.discussion.max_rounds or 10,
        response_callback=on_message,
        supports_structured_output=config.supports_structured_output,
        selection_prompt=config.discussion.selection_prompt,
        termination_prompt=config.discussion.termination_prompt,
        result_filter_prompt=config.discussion.result_filter_prompt,
    )

    discussion_transcript = build_discussion_transcript(history)

    if final_agents:
        print("\n=== FINAL SUMMARY AGENTS ===")
        for ac, agent in final_agents:
            response = await agent.get_response(
                messages=[ChatMessageContent(
                    role=AuthorRole.USER,
                    content=f"以下是完整讨论记录，请按你的格式要求输出总结：\n\n{discussion_transcript}",
                )],
            )
            on_message(response.message)

    print("\n=== VOTING ===")
    voting_result = await run_voting(
        agents=discussion_agents,
        topic=TEST_TOPIC,
        discussion_context=discussion_transcript,
        voting_prompt=config.voting.prompt,
    )

    for vote in voting_result.votes:
        icon = "+" if vote.stance == "赞成" else ("-" if vote.stance == "反对" else "~")
        print(f"  [{icon}] {vote.agent_name}: {vote.stance} (confidence={vote.confidence:.1f})")
        print(f"      {vote.reason[:200]}")

    print(f"\n  Conclusion: {voting_result.conclusion}")

    elapsed = time.time() - t0

    result = {
        "topic": TEST_TOPIC,
        "config": config_name,
        "elapsed_seconds": round(elapsed, 1),
        "messages": messages,
        "discussion_transcript": discussion_transcript,
        "summary": summary,
        "votes": [v.model_dump() for v in voting_result.votes],
        "conclusion": voting_result.conclusion,
    }

    tag = config_name.replace(".yaml", "").replace("agents_", "").replace("agents", "baseline")
    out_path = Path(__file__).resolve().parent.parent / "scripts" / f"{tag}_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== DONE in {elapsed:.1f}s ===")
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
