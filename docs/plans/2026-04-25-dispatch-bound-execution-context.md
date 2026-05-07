# Context Snapshot: Dispatch-Bound Execution

Task statement:
- Choose the recommended design: dispatch-bound execution for agora.

Desired outcome:
- Keep the Host responsible for task complexity analysis and dispatch planning.
- Make Host dispatch executable, so selected agents, assigned tasks, synthesis, and voting follow the dispatch plan.
- Produce a final solution that is clearly separate from voting/review output.

Known facts and evidence:
- Session `/Users/lvzhibo/Agent/agora/sessions/modps4lm.json` shows the current mismatch.
- Host generated a medium-complexity dispatch plan with invented roles such as `SecurityProcessAgent`, `BackendCommunicationAgent`, `RiskTriageAgent`, `ReproductionEvidenceAgent`, and `RemediationValidationAgent`.
- Actual discussion still ran the configured fixed agents: `Architect`, `Pragmatist`, and `Challenger`.
- The discussion pipeline forces at least one turn per configured discussion agent through `min_rounds_floor = max(1, len(agents))`.
- `Synthesizer` produced an empty final message, so the user had to prompt again before a usable answer appeared.
- Voting ran over discussion context and displayed as if it were the final conclusion, which made the final answer ambiguous.
- Voting agent names currently trust model JSON, producing names like `DevilsAdvocate` instead of the configured `Challenger`.

Constraints:
- Preserve current React + TypeScript + CSS Modules frontend architecture.
- Keep the existing Semantic Kernel fixed-agent configuration for the first implementation pass.
- Do not introduce new dependencies.
- Changes should stay small, testable, and reversible.
- Backend must log/validate model-generated dispatch data because it is untrusted.

Unknowns:
- Whether Semantic Kernel agents can be cheaply cloned with per-agent instruction overlays in the current version.
- Whether the product should expose direct mode in UI immediately or only implement it as backend behavior.
- Whether Host complexity thresholds should be configurable by environment or hardcoded initially.

Likely codebase touchpoints:
- `src/models.py`
- `src/brainstorm.py`
- `src/web_server.py`
- `src/discussion.py`
- `src/voting.py`
- `tests/test_pipeline_and_voting.py`
- `scripts/e2e_discussion_ws.py`
- `frontend/src/types.ts`
- `frontend/src/components/Timeline/VotingCard.tsx`
- `frontend/src/components/Timeline/HostMessage.tsx`
- `frontend/src/components/Progress/AgentStatusPanel.tsx`
