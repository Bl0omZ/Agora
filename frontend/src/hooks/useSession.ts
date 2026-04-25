import { useState, useEffect, useCallback, useRef } from 'react';
import type { SessionData, SessionIndexEntry, Message, PhaseEvent, VotingResult, PipelineLog } from '../types';
import { SessionManager } from '../utils/session';

interface UseSessionReturn {
  sessions: SessionIndexEntry[];
  currentSessionId: string | null;
  isHistoryMode: boolean;
  createSession: (topic: string) => string;
  updateSessionData: (partial: {
    messages?: Message[];
    phases?: PhaseEvent[];
    votingResult?: VotingResult | null;
    logs?: PipelineLog[];
    savedPath?: string | null;
  }) => void;
  loadHistorySession: (id: string) => SessionData | null;
  loadHistorySessionAsync: (id: string) => Promise<SessionData | null>;
  startNewSession: () => void;
  deleteSession: (id: string) => void;
  syncToServer: (sessionData: SessionData) => Promise<void>;
}

export function useSession(): UseSessionReturn {
  const [sessions, setSessions] = useState<SessionIndexEntry[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isHistoryMode, setIsHistoryMode] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // Merge local + remote sessions, dedup by id, prefer the one with newer updatedAt
  const mergeSessions = useCallback((
    local: SessionIndexEntry[],
    remote: SessionIndexEntry[],
  ): SessionIndexEntry[] => {
    const map = new Map<string, SessionIndexEntry>();
    for (const s of local) map.set(s.id, s);
    for (const s of remote) {
      const existing = map.get(s.id);
      if (!existing || s.updatedAt > existing.updatedAt) {
        map.set(s.id, s);
      }
    }
    return Array.from(map.values()).sort((a, b) => b.updatedAt - a.updatedAt);
  }, []);

  const refreshIndex = useCallback(async () => {
    const local = SessionManager.listSessions();
    setSessions(local); // Show local immediately for fast paint
    try {
      const res = await fetch('/api/sessions');
      const data = await res.json();
      const remote: SessionIndexEntry[] = data.sessions ?? [];
      setSessions(mergeSessions(local, remote));
    } catch (error) {
      console.warn('Failed to fetch remote sessions:', error);
    }
  }, [mergeSessions]);

  useEffect(() => {
    refreshIndex();
  }, [refreshIndex]);

  const createSession = useCallback((topic: string): string => {
    const newSession = SessionManager.createEmptySession(topic);
    SessionManager.saveSession(newSession);
    setCurrentSessionId(newSession.id);
    setIsHistoryMode(false);
    refreshIndex();
    return newSession.id;
  }, [refreshIndex]);

  const updateSessionData = useCallback((partial: {
    messages?: Message[];
    phases?: PhaseEvent[];
    votingResult?: VotingResult | null;
    logs?: PipelineLog[];
    savedPath?: string | null;
  }) => {
    if (!currentSessionId || isHistoryMode) return;

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      const existing = SessionManager.loadSession(currentSessionId);
      if (!existing) return;
      const updated: SessionData = {
        ...existing,
        ...(partial.messages !== undefined && { messages: partial.messages }),
        ...(partial.phases !== undefined && { phases: partial.phases }),
        ...(partial.votingResult !== undefined && { votingResult: partial.votingResult }),
        ...(partial.logs !== undefined && { logs: partial.logs }),
        ...(partial.savedPath !== undefined && { savedPath: partial.savedPath }),
        updatedAt: Date.now(),
      };
      SessionManager.saveSession(updated);
      refreshIndex();
    }, 500);
  }, [currentSessionId, isHistoryMode, refreshIndex]);

  const loadHistorySession = useCallback((id: string): SessionData | null => {
    const data = SessionManager.loadSession(id);
    if (data) {
      setCurrentSessionId(id);
      setIsHistoryMode(true);
    }
    return data;
  }, []);

  // Async version: try local first, fallback to remote and cache locally
  const loadHistorySessionAsync = useCallback(async (id: string): Promise<SessionData | null> => {
    const local = SessionManager.loadSession(id);
    if (local) {
      setCurrentSessionId(id);
      setIsHistoryMode(true);
      return local;
    }
    try {
      const res = await fetch(`/api/sessions/${id}`);
      if (!res.ok) return null;
      const data: SessionData = await res.json();
      // Cache to localStorage so next load is instant
      SessionManager.saveSession(data);
      setCurrentSessionId(id);
      setIsHistoryMode(true);
      refreshIndex();
      return data;
    } catch (error) {
      console.error('Failed to load session from remote:', error);
      return null;
    }
  }, [refreshIndex]);

  const startNewSession = useCallback(() => {
    setCurrentSessionId(null);
    setIsHistoryMode(false);
  }, []);

  const deleteSession = useCallback((id: string) => {
    SessionManager.deleteSession(id);
    refreshIndex();
    if (currentSessionId === id) {
      setCurrentSessionId(null);
      setIsHistoryMode(false);
    }
  }, [currentSessionId, refreshIndex]);

  const syncToServer = useCallback(async (sessionData: SessionData) => {
    try {
      await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sessionData),
      });
    } catch (error) {
      console.error('Failed to sync session to server:', error);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  return {
    sessions, currentSessionId, isHistoryMode,
    createSession, updateSessionData,
    loadHistorySession, loadHistorySessionAsync,
    startNewSession, deleteSession, syncToServer,
  };
}
