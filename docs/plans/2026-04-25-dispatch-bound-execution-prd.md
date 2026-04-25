# PRD: Dispatch-Bound Execution

## Goal

Make the Host's complexity analysis and dispatch plan control the real session pipeline. The Host can still analyze the task and assign work, but the backend must bind that dispatch to selected agents, discussion scope, synthesis, review, followup, and exported session data.

## Problem

Current behavior treats `dispatch_plan` as display metadata. In `sessions/modps4lm.json`, the Host assigned invented roles, while the real discussion still ran the fixed `Architect`, `Pragmatist`, and `Challenger` agents. The final synthesis was empty, and voting appeared to be the final conclusion even though it was only a review signal.

## Decision

Use **fixed agent pool + dispatch-bound execution** for the first implementation pass.

- Do not dynamically create new agents.
- Do not clone agents with temporary instructions yet.
- Host may choose only configured discussion agents.
- Backend normalizes Host output into a trusted session execution state.
- Final solution is the primary user artifact.
- Voting becomes a secondary proposal review.

## Principles

- Dispatch must be executable, not cosmetic.
- Backend-controlled names and modes are trusted; model JSON is not trusted.
- Simple tasks should be allowed to skip multi-agent discussion.
- Final solution must be visible and non-empty before review starts.
- Existing sessions and exports must remain readable.

## Decision Drivers

- Align product behavior with the user's expectation: different roles/models discuss only when useful.
- Reduce noisy all-agent runs for simple tasks.
- Prevent voting/review from obscuring the final answer.

## State Contract

Add a normalized backend state, either as `BrainstormOutcome` or `SessionDispatchState`, and persist it on `SessionState`.

Required fields:

- `original_topic`: original user topic; written when session starts; never empty.
- `refined_topic`: Host-refined topic; may equal `original_topic` if brainstorming is skipped or fails.
- `complexity`: normalized Host complexity; allowed values `simple`, `medium`, `complex`; fallback `medium`.
- `execution_mode`: normalized execution mode; allowed values `direct`, `focused`, `panel`.
- `dispatch_plan`: UI-safe normalized plan, after whitelist filtering.
- `selected_agents`: ordered list of real configured discussion agent names; empty only when `execution_mode=direct`.
- `agent_tasks`: map keyed by real agent name; each value contains `task`, `expected_output`, optional `rationale`.
- `expected_final_output`: Host's requested final output shape; fallback to a default final answer contract.
- `final_solution`: synthesis output; written before review; must not be overwritten by review.
- `review_result`: voting/review output; written after `final_solution`.

Compatibility:

- Old session files missing these fields should load with derived fallback values.
- API payloads should omit no required display data; missing legacy fields must not break the UI.

## Dispatch Rules

Backend whitelist:

- Allow only configured discussion agents.
- Exclude manager agents.
- Exclude `final_only` agents from `selected_agents`.
- Deduplicate while preserving configured agent order.
- Log invented, excluded, or duplicate names.

Fallback:

- If Host output is invalid and complexity is `simple`, use `execution_mode=direct`.
- If Host output is invalid and complexity is `medium` or `complex`, use `execution_mode=panel` with all configured discussion agents in config order.
- If Host provides valid agents but no mode, infer `focused` when selected count is less than all discussion agents, otherwise `panel`.

## Pipeline Behavior

- Brainstorming returns normalized state, not just a topic string.
- `direct`: skip discussion, run synthesis from topic + expected output.
- `focused`: run only `selected_agents`.
- `panel`: run selected agents, or all configured discussion agents after fallback.
- `run_discussion` receives only selected agent objects.
- `min_rounds` is calculated from the selected list.
- Unselected agents must not receive prompts, emit WebSocket thinking/message events, appear in transcript, or participate in review.
- Discussion prompt includes a dispatch brief and per-agent task list.

## Synthesis

Create an explicit synthesis phase.

Inputs:

- original topic
- refined topic
- complexity
- normalized dispatch plan
- expected final output
- discussion transcript, if any

Output:

- `final_solution`, with a clear final recommendation and directly usable content.

Failure handling:

- Empty model output retries once with a stricter prompt.
- If still empty, create a deterministic fallback summary from known state.
- Fallback must remove hidden reasoning and mark that it was generated from available session data.

## Review / Voting

Voting becomes proposal review.

- Review input is `final_solution`, not raw discussion transcript.
- Review must not overwrite `final_solution`.
- `vote.agent_name` is forced from the real invoked agent name.
- Review agents are the same selected discussion agents for focused/panel; direct mode may skip review or use configured default reviewers if explicitly enabled.
- UI labels should say `方案评审` and `评审结论`, not `最终结论`.

## Followup / Report / Export

- Followup should reuse the existing dispatch state by default.
- Followup must not silently expand back to all agents.
- Export/report should include original topic, refined topic, complexity, execution mode, selected agents, final solution, and review result.
- Legacy sessions without normalized state should display fallback metadata.

## Frontend Scope

- Extend TypeScript types for the normalized dispatch state.
- Render Host dispatch from normalized data only.
- Show final solution as the primary artifact.
- Show review below final solution as secondary evaluation.
- Mark unselected agents as not dispatched, or omit them from active execution views.
- Keep existing React + TypeScript + CSS Modules architecture.

## Alternatives

1. Prompt-only dispatch brief while still running all agents.
   - Lower implementation risk.
   - Rejected because dispatch remains a soft constraint and does not solve the user's core issue.

2. Dynamic agent creation from Host dispatch.
   - More flexible and closer to an autonomous moderator.
   - Rejected for first pass because service/model mapping, UI identity, logging, and failure handling become much larger.

3. Fixed agent pool with dispatch-bound execution.
   - Chosen because it makes dispatch real while keeping the current architecture stable.

## ADR

Decision:
- Implement fixed-pool dispatch-bound execution.

Drivers:
- Host decisions must affect runtime behavior.
- Final answer must be distinct from review.
- The first pass must be small enough to test reliably.

Why chosen:
- It addresses the observed mismatch without introducing dynamic agent lifecycle complexity.

Consequences:
- Host can only select existing agents.
- Some semantic roles suggested by Host may be remapped or dropped.
- Future dynamic agents can be added after the fixed-pool contract is stable.

Follow-ups:
- Add configurable complexity thresholds.
- Consider per-agent instruction overlays if Semantic Kernel supports safe cloning.
- Add UI controls for rerun/re-dispatch after a session.

## Available Agent Types

- `explore`: codebase mapping.
- `architect`: architecture review.
- `critic`: plan and quality challenge.
- `executor`: implementation.
- `test-engineer`: test design and E2E coverage.
- `verifier`: completion evidence.
- `code-reviewer`: final code review.

## Execution Guidance

Sequential route:
- Use `ralph` for one implementation lane: backend state and pipeline, then frontend semantics, then tests.

Parallel route:
- Use `team` only after the PRD/test spec are accepted.
- Backend executor owns `src/models.py`, `src/brainstorm.py`, `src/web_server.py`, `src/discussion.py`, `src/voting.py`.
- Frontend executor owns `frontend/src/types.ts`, Host timeline components, progress panel, voting card.
- Test engineer owns unit, WS integration, and E2E updates.
- Verifier runs backend tests, frontend build, and one real or mocked security-ticket flow.

Suggested reasoning:
- Backend executor: high.
- Frontend executor: medium.
- Test engineer: high.
- Verifier: high.

## Acceptance Criteria

- Host dispatch cannot execute invented agent names.
- Focused mode runs only selected agents.
- Direct mode produces a non-empty final solution without discussion.
- Final solution appears before review.
- Review never overwrites or replaces final solution.
- Voting/review names always match configured agent names.
- The security-ticket E2E flow ends with a usable final proposal and no hidden reasoning text.
