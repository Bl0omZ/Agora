import { useState, useEffect, useRef, useCallback } from 'react';
import type {
  AgentInfo, Message, PhaseEvent, VotingResult,
  AgentState, RoundProgress, PipelineLog, DiscussionConfig,
  DiscussionPhase, BrainstormQuestion, BrainstormAnswer,
  TopicRefinedPayload, BrainstormFailureState, AgentSystemBlueprint,
  PresetRecommendation,
} from '../types';

export type ConnectionStatus = 'disconnected' | 'connected' | 'error';

const CLIENT_SESSION_STORAGE_KEY = 'agent-discussion-client-session-id';

function createClientSessionId(): string {
  const cryptoApi = window.crypto;
  if (cryptoApi?.randomUUID) {
    return cryptoApi.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getClientSessionId(): string {
  const existing = window.sessionStorage.getItem(CLIENT_SESSION_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const next = createClientSessionId();
  window.sessionStorage.setItem(CLIENT_SESSION_STORAGE_KEY, next);
  return next;
}

export interface WebSocketState {
  connectionStatus: ConnectionStatus;
  messages: Message[];
  phases: PhaseEvent[];
  agents: AgentInfo[];
  agentStates: Record<string, AgentState>;
  votingResult: VotingResult | null;
  blueprint: AgentSystemBlueprint | null;
  blueprintWarnings: string[];
  isReady: boolean;
  currentTopic: string;
  currentPhase: DiscussionPhase;
  roundProgress: RoundProgress | null;
  logs: PipelineLog[];
  error: string | null;
  savedPath: string | null;
  pendingQuestion: BrainstormQuestion | null;
  pendingTopicRefined: TopicRefinedPayload | null;
  pendingPreset: PresetRecommendation | null;
  brainstormFailure: BrainstormFailureState | null;
  isBrainstormSubmitting: boolean;

  send: (data: Record<string, unknown>) => void;
  startDiscussion: (topic: string, config?: DiscussionConfig, sessionId?: string) => void;
  sendFollowup: (message: string) => void;
  saveReport: (topic: string) => void;
  submitBrainstormAnswer: (answer: BrainstormAnswer) => void;
  skipBrainstorm: () => void;
  confirmTopic: () => void;
  confirmPreset: (presetName: string) => void;
  refineTopicAgain: () => void;
  dismissBrainstormFailure: () => void;
}

export function useWebSocket(): WebSocketState {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(false);
  const clientSessionIdRef = useRef(getClientSessionId());
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [messages, setMessages] = useState<Message[]>([]);
  const [phases, setPhases] = useState<PhaseEvent[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [agentStates, setAgentStates] = useState<Record<string, AgentState>>({});
  const [votingResult, setVotingResult] = useState<VotingResult | null>(null);
  const [blueprint, setBlueprint] = useState<AgentSystemBlueprint | null>(null);
  const [blueprintWarnings, setBlueprintWarnings] = useState<string[]>([]);
  const [isReady, setIsReady] = useState(false);
  const [currentTopic, setCurrentTopic] = useState('');
  const [currentPhase, setCurrentPhase] = useState<DiscussionPhase>('idle');
  const [roundProgress, setRoundProgress] = useState<RoundProgress | null>(null);
  const [logs, setLogs] = useState<PipelineLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [savedPath, setSavedPath] = useState<string | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<BrainstormQuestion | null>(null);
  const [pendingTopicRefined, setPendingTopicRefined] = useState<TopicRefinedPayload | null>(null);
  const [pendingPreset, setPendingPreset] = useState<PresetRecommendation | null>(null);
  const [brainstormFailure, setBrainstormFailure] = useState<BrainstormFailureState | null>(null);
  const [isBrainstormSubmitting, setIsBrainstormSubmitting] = useState(false);
  const messageIdRef = useRef(0);

  const connect = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    const socket = new WebSocket(wsUrl);
    wsRef.current = socket;

    socket.onopen = () => {
      if (wsRef.current !== socket) return;
      setConnectionStatus('connected');
      setError(null);
    };

    socket.onclose = () => {
      if (wsRef.current !== socket) return;
      wsRef.current = null;
      setConnectionStatus('disconnected');
      if (shouldReconnectRef.current) {
        reconnectTimerRef.current = window.setTimeout(connect, 3000);
      }
    };

    socket.onerror = () => {
      if (wsRef.current !== socket) return;
      setConnectionStatus('error');
    };

    socket.onmessage = (event) => {
      if (wsRef.current !== socket) return;
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'agents':
          setAgents(data.agents);
          break;

        case 'agent_meta':
          setAgents(prev => {
            const byName = new Map(prev.map(agent => [agent.name, agent]));
            return data.agents.map((agent: AgentInfo & { role?: string }) => {
              const existing = byName.get(agent.name);
              return {
                name: agent.name,
                description: existing?.description ?? agent.description ?? agent.role ?? '',
                model: agent.model,
                final_only: existing?.final_only ?? agent.final_only ?? false,
                is_moderator: agent.is_moderator,
              };
            });
          });
          break;

        case 'phase': {
          const phaseValue = data.phase as string;
          setPhases(prev => [...prev, { phase: phaseValue, label: data.label, timestamp: Date.now() }]);
          if (['brainstorming', 'discussion', 'synthesis', 'blueprint', 'voting', 'followup', 'followup_round'].includes(phaseValue)) {
            setCurrentPhase(phaseValue as DiscussionPhase);
          }
          break;
        }

        case 'message': {
          messageIdRef.current += 1;
          const newMsg: Message = {
            id: messageIdRef.current,
            name: data.name,
            content: data.content,
            phase: data.phase,
            role: data.role ?? 'assistant',
            timestamp: Date.now(),
            meta: data.meta,
          };
          setMessages(prev => {
            // De-dup: if last message has same name + content, skip
            const last = prev[prev.length - 1];
            if (last && last.name === newMsg.name && last.content === newMsg.content && last.phase === newMsg.phase) {
              return prev;
            }
            return [...prev, newMsg];
          });
          setAgentStates(prev => {
            const agentName = data.name;
            const existing = prev[agentName];
            return {
              ...prev,
              [agentName]: {
                name: agentName,
                status: 'spoken',
                speakCount: (existing?.speakCount ?? 0) + 1,
              },
            };
          });
          break;
        }

        case 'voting_result':
          setVotingResult(data as VotingResult);
          break;

        case 'blueprint':
          setBlueprint(data.blueprint as AgentSystemBlueprint);
          setBlueprintWarnings(data.warnings ?? []);
          break;

        case 'blueprint_warning':
          setBlueprintWarnings(data.warnings ?? []);
          break;

        case 'round_progress':
          setRoundProgress({ current: data.current, total: data.total });
          break;

        case 'agent_status':
          setAgentStates(prev => {
            const existing = prev[data.name];
            // Don't overwrite 'spoken' with 'skipped' (defensive)
            if (existing?.status === 'spoken' && data.status === 'skipped') {
              return prev;
            }
            return {
              ...prev,
              [data.name]: {
                name: data.name,
                status: data.status,
                speakCount: existing?.speakCount ?? 0,
              },
            };
          });
          break;

        case 'pipeline_log':
          setLogs(prev => [...prev, {
            phase: data.phase,
            event: data.event,
            timestamp: Date.now(),
            durationMs: data.duration_ms,
            tokens: data.tokens,
            detail: data.detail,
          }]);
          break;

        case 'moderator_question':
          setPendingQuestion(data as BrainstormQuestion);
          setPendingTopicRefined(null);
          setIsBrainstormSubmitting(false);
          break;

        case 'topic_refined':
          setPendingTopicRefined(data as TopicRefinedPayload);
          setPendingQuestion(null);
          setPendingPreset(null);
          setIsBrainstormSubmitting(false);
          break;

        case 'preset_recommended':
          setPendingPreset({
            recommended: data.preset_name,
            presets: data.all_presets ?? [],
          });
          setPendingQuestion(null);
          setPendingTopicRefined(null);
          setIsBrainstormSubmitting(false);
          break;

        case 'preset_confirmed':
          setPendingPreset(null);
          setIsBrainstormSubmitting(false);
          break;

        case 'brainstorm_timeout':
          setBrainstormFailure({ kind: 'timeout' });
          setPendingQuestion(null);
          setPendingPreset(null);
          setIsBrainstormSubmitting(false);
          break;

        case 'started':
          setCurrentTopic(data.topic);
          setMessages([]);
          setPhases([]);
          setVotingResult(null);
          setBlueprint(null);
          setBlueprintWarnings([]);
          setIsReady(false);
          setError(null);
          setSavedPath(null);
          setRoundProgress(null);
          setLogs([]);
          setAgentStates({});
          setPendingQuestion(null);
          setPendingTopicRefined(null);
          setPendingPreset(null);
          setBrainstormFailure(null);
          setIsBrainstormSubmitting(false);
          setCurrentPhase('brainstorming');
          break;

        case 'ready':
          setIsReady(true);
          setPendingQuestion(null);
          setPendingTopicRefined(null);
          setPendingPreset(null);
          setIsBrainstormSubmitting(false);
          setCurrentPhase('done');
          break;

        case 'saved':
          setSavedPath(data.path);
          break;

        case 'error':
          setError(data.message);
          setIsReady(true);
          break;
      }
    };

  }, []);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();
    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      const socket = wsRef.current;
      wsRef.current = null;
      socket?.close();
    };
  }, [connect]);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        ...data,
        client_session_id: clientSessionIdRef.current,
      }));
    }
  }, []);

  const startDiscussion = useCallback((topic: string, config?: DiscussionConfig, sessionId?: string) => {
    send({ action: 'start', topic, config: config ?? undefined, session_id: sessionId });
  }, [send]);

  const sendFollowup = useCallback((message: string) => {
    send({ action: 'followup', message });
  }, [send]);

  const saveReport = useCallback((topic: string) => {
    send({ action: 'save', topic });
  }, [send]);

  const submitBrainstormAnswer = useCallback((answer: BrainstormAnswer) => {
    setPendingQuestion(null);
    setIsBrainstormSubmitting(true);
    send({ action: 'moderator_answer', ...answer });
  }, [send]);

  const skipBrainstorm = useCallback(() => {
    setPendingQuestion(null);
    setPendingTopicRefined(null);
    setPendingPreset(null);
    setBrainstormFailure({ kind: 'skipped' });
    setIsBrainstormSubmitting(false);
    send({ action: 'brainstorm_skip' });
  }, [send]);

  const confirmTopic = useCallback(() => {
    setPendingTopicRefined(null);
    setIsBrainstormSubmitting(false);
    send({ action: 'topic_confirmed', accept: true });
  }, [send]);

  const confirmPreset = useCallback((presetName: string) => {
    setPendingPreset(null);
    setIsBrainstormSubmitting(false);
    send({ action: 'preset_confirmed', preset_name: presetName });
  }, [send]);

  const refineTopicAgain = useCallback(() => {
    setPendingTopicRefined(null);
    setPendingPreset(null);
    setIsBrainstormSubmitting(true);
    send({ action: 'topic_refine_again' });
  }, [send]);

  const dismissBrainstormFailure = useCallback(() => {
    setBrainstormFailure(null);
  }, []);

  return {
    connectionStatus, messages, phases, agents, agentStates,
    votingResult, blueprint, blueprintWarnings, isReady, currentTopic, currentPhase,
    roundProgress, logs, error, savedPath,
    pendingQuestion, pendingTopicRefined, pendingPreset, brainstormFailure, isBrainstormSubmitting,
    send, startDiscussion, sendFollowup, saveReport,
    submitBrainstormAnswer, skipBrainstorm, confirmTopic, confirmPreset, refineTopicAgain,
    dismissBrainstormFailure,
  };
}
