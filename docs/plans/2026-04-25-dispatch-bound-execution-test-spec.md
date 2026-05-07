# Test Spec: Dispatch-Bound Execution

## Verification Goal

Prove that Host dispatch controls execution, final synthesis is the primary artifact, and proposal review cannot be mistaken for the final answer.

## Unit Tests

### Dispatch Normalization

- Invented agent names are removed and logged.
- Manager agents are excluded.
- `final_only` agents are excluded from `selected_agents`.
- Duplicate agent names are deduplicated in configured order.
- Missing mode is inferred from selected count.
- Invalid simple dispatch falls back to `direct`.
- Invalid medium/complex dispatch falls back to `panel` with configured discussion agents.
- Normalized dispatch serializes to frontend-safe JSON.

### Pipeline Selection

- `direct` mode does not call `run_discussion`.
- `focused` mode passes only selected agent objects to `run_discussion`.
- `panel` fallback uses configured discussion agents in deterministic order.
- `min_rounds` is based on selected agents only.
- Unselected agents are absent from transcript and message queue.

### Synthesis

- Synthesis prompt includes original topic, refined topic, dispatch plan, expected final output, and transcript when present.
- Empty synthesis output retries once.
- Retry failure creates a non-empty deterministic fallback.
- Fallback strips `<think>` and other hidden reasoning.
- `final_solution` is written before review.

### Review / Voting

- Review receives `final_solution`, not raw discussion transcript.
- Review does not mutate `final_solution`.
- `vote.agent_name` is overwritten with the configured agent name.
- Model-provided aliases such as `DevilsAdvocate` cannot appear in final review data unless configured.
- Direct mode review behavior is deterministic: skipped or explicitly defaulted according to config.

### Legacy Compatibility

- Old sessions without dispatch state load without error.
- Export/report can render sessions with missing `final_solution` or `review_result`.

## Integration / WebSocket Tests

### Focused Dispatch

Fixture:
- Host returns `execution_mode=focused`.
- `selected_agents=["Architect"]`.

Expected:
- Only Architect emits thinking/message events.
- Pragmatist and Challenger emit no thinking/message events.
- Transcript contains no Pragmatist or Challenger entry.
- Review uses only configured selected reviewers, or the documented default review path.

### Invalid Host Dispatch

Fixture:
- Host returns invented names only.

Expected:
- Backend logs invalid names.
- Normalized dispatch contains only real configured agents or direct fallback.
- UI receives normalized names only.
- No invented name appears as an executing agent.

### Direct Mode

Fixture:
- Host classifies the task as simple/direct.

Expected:
- Discussion phase is skipped.
- Final solution is emitted.
- Review is skipped or runs through the configured direct-mode review rule.
- Session completes without empty assistant messages.

### Final Solution Before Review

Expected event order:

1. brainstorm/dispatch events
2. optional discussion events
3. final solution event
4. proposal review event
5. completion event

Review must not appear as the only final artifact.

### Followup / Export

Expected:
- Followup reuses current dispatch state unless a new explicit dispatch is requested.
- Followup does not silently expand selected agents to all agents.
- Export includes execution mode, selected agents, final solution, and review result.
- Legacy export still succeeds.

## E2E Scenario

Prompt:

```text
作为安全工程师需要发送漏洞工单给研发，需要在安全工单中输出哪些内容可以保证清晰易懂
```

Mode:

- Use fixed or mocked Host dispatch for deterministic CI.
- Random-answer manual mode can remain as a smoke script, but should not be the only regression check.

Expected:

- Brainstorm completes or is skipped by test fixture.
- Dispatch is normalized.
- Executed agent set matches normalized dispatch.
- Final solution is non-empty and includes a concrete security-ticket content structure.
- Review result exists when review is enabled.
- UI separates final solution from proposal review.
- Output contains no `<think>` content.
- No invented agent name appears as an executing participant.

## Commands

Backend:

```bash
pytest tests/test_pipeline_and_voting.py
```

Frontend:

```bash
cd frontend
npm run build
```

E2E:

```bash
python scripts/e2e_discussion_ws.py --topic "作为安全工程师需要发送漏洞工单给研发，需要在安全工单中输出哪些内容可以保证清晰易懂"
```

## Done Criteria

- Unit tests cover dispatch normalization, execution selection, synthesis fallback, review input, and legacy compatibility.
- WebSocket tests prove unselected agents do not execute.
- Frontend build passes.
- E2E produces a non-empty final solution and separated proposal review.
- Known issue from `modps4lm.json` cannot recur: invented Host roles must not execute, all fixed agents must not run for a focused dispatch, and empty synthesis must not be accepted as final output.
