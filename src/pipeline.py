"""Pipeline: orchestrates discussion → voting → follow-up → confirmation."""

import logging

from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent

from .loader import create_agent, create_service, resolve_preset
from .discussion import build_discussion_transcript, run_discussion, run_followup
from .models import AppConfig
from .reporting import get_default_report_dir, save_report
from .voting import run_voting

logger = logging.getLogger(__name__)


async def run_pipeline(config: AppConfig, topic: str) -> None:
    """Main pipeline: discussion → final agents → voting → follow-up loop → confirmation."""

    manager_config = config.agents[config.manager_service_index]
    selected_discussion_names = {agent.name for agent in resolve_preset(config)}
    # Separate discussion agents from final_only agents
    discussion_agents = []
    final_agents = []
    for index, ac in enumerate(config.agents):
        if index == config.manager_service_index:
            continue
        if ac.final_only:
            agent = create_agent(ac)
            final_agents.append((ac, agent))
        elif ac.name in selected_discussion_names:
            agent = create_agent(ac)
            discussion_agents.append(agent)
        else:
            logger.info("Skipping agent not in default preset: %s", ac.name)

    manager_service = create_service(manager_config)

    discussion_result = None
    history = ChatHistory()
    discussion_transcript = ""
    voting_result = None

    def on_message(msg: ChatMessageContent) -> None:
        print(f"\n  **{msg.name}**\n  {msg.content}\n")

    # 3. Discussion phase (excluding final_only agents)
    if config.discussion.enabled:
        print("\n" + "=" * 60)
        print("  讨论阶段")
        print("=" * 60)

        discussion_result, history = await run_discussion(
            agents=discussion_agents,
            topic=topic,
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

        # 3.5 Invoke final_only agents (e.g. Synthesizer)
        if final_agents:
            print("\n" + "=" * 60)
            print("  最终总结")
            print("=" * 60)
            for ac, agent in final_agents:
                response = await agent.get_response(
                    messages=[ChatMessageContent(
                        role=AuthorRole.USER,
                        content=f"以下是完整讨论记录，请按你的格式要求输出总结：\n\n{discussion_transcript}",
                    )],
                )
                on_message(response.message)
                history.add_message(response.message)
                discussion_result = response.message.content or discussion_result

        print("\n" + "=" * 60)
        print("  讨论摘要")
        print("=" * 60)
        print(f"\n  {discussion_result}\n")

    # 4. Voting phase
    if config.voting.enabled:
        print("=" * 60)
        print("  投票阶段")
        print("=" * 60)

        voting_result = await run_voting(
            agents=discussion_agents,
            topic=topic,
            discussion_context=discussion_transcript or discussion_result or "",
            voting_prompt=config.voting.prompt,
        )

        print()
        support_count = 0
        oppose_count = 0
        for vote in voting_result.votes:
            icon = "+" if vote.stance == "赞成" else ("-" if vote.stance == "反对" else "~")
            print(f"  [{icon}] {vote.agent_name}: {vote.stance} ({vote.reason}) [置信度: {vote.confidence:.1f}]")
            if vote.stance == "赞成":
                support_count += 1
            elif vote.stance == "反对":
                oppose_count += 1

        print(
            f"\n  票数：{support_count} 赞成 / {oppose_count} 反对 / "
            f"{len(voting_result.votes) - support_count - oppose_count} 中立"
        )
        print(f"  结论：{voting_result.conclusion}")

    # 5. Follow-up loop
    print("\n" + "=" * 60)
    print("  后续交互（输入你的问题，或输入 y 确认 / q 退出）")
    print("=" * 60)

    while True:
        user_input = input("\n  > ").strip()
        if not user_input:
            continue
        if user_input.lower() == "y":
            report_path = save_report(
                topic=topic,
                discussion_summary=discussion_result or "",
                discussion_transcript=discussion_transcript,
                voting_result=voting_result,
                output_dir=get_default_report_dir(),
            )
            print(f"  报告已保存：{report_path}")
            print("  结果已确认。再见。")
            break
        if user_input.lower() == "q":
            print("  已退出。")
            break

        # Run follow-up discussion
        print()
        history = await run_followup(
            agents=discussion_agents,
            history=history,
            followup_message=user_input,
            manager_service=manager_service,
            manager_name=manager_config.name,
            manager_instructions=manager_config.instructions,
            response_callback=on_message,
            max_rounds=config.discussion.max_rounds or 5,
            supports_structured_output=config.supports_structured_output,
            selection_prompt=config.discussion.selection_prompt,
            termination_prompt=config.discussion.termination_prompt,
            result_filter_prompt=config.discussion.result_filter_prompt,
        )
        print("\n  --- 本轮追问已完成，可继续提问，或输入 y / q。 ---")
