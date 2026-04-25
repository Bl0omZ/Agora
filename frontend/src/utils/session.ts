import type { SessionData, SessionIndexEntry } from '../types';
import { SCHEMA_VERSION, SESSION_INDEX_KEY, SESSION_PREFIX, MAX_SESSIONS } from '../constants';

export const SessionManager = {
  listSessions(): SessionIndexEntry[] {
    try {
      const raw = localStorage.getItem(SESSION_INDEX_KEY);
      if (!raw) return [];
      const sessions: SessionIndexEntry[] = JSON.parse(raw);
      return sessions.sort((a, b) => b.updatedAt - a.updatedAt);
    } catch {
      return [];
    }
  },

  loadSession(id: string): SessionData | null {
    try {
      const raw = localStorage.getItem(`${SESSION_PREFIX}${id}`);
      if (!raw) return null;
      return JSON.parse(raw) as SessionData;
    } catch {
      return null;
    }
  },

  saveSession(data: SessionData): void {
    try {
      localStorage.setItem(`${SESSION_PREFIX}${data.id}`, JSON.stringify(data));
      const index = this.listSessions();
      const existingPosition = index.findIndex(s => s.id === data.id);
      const entry: SessionIndexEntry = {
        id: data.id,
        topic: data.topic,
        messageCount: data.messages.length,
        createdAt: data.createdAt,
        updatedAt: Date.now(),
      };
      if (existingPosition >= 0) {
        index[existingPosition] = entry;
      } else {
        index.push(entry);
      }
      index.sort((a, b) => b.updatedAt - a.updatedAt);
      if (index.length > MAX_SESSIONS) {
        index.slice(MAX_SESSIONS).forEach(s => localStorage.removeItem(`${SESSION_PREFIX}${s.id}`));
      }
      localStorage.setItem(SESSION_INDEX_KEY, JSON.stringify(index.slice(0, MAX_SESSIONS)));
    } catch (error) {
      console.error('Failed to save session:', error);
    }
  },

  deleteSession(id: string): void {
    try {
      localStorage.removeItem(`${SESSION_PREFIX}${id}`);
      const index = this.listSessions().filter(s => s.id !== id);
      localStorage.setItem(SESSION_INDEX_KEY, JSON.stringify(index));
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  },

  createEmptySession(topic: string): SessionData {
    const now = Date.now();
    return {
      schemaVersion: SCHEMA_VERSION,
      id: now.toString(36),
      topic,
      messages: [],
      phases: [],
      votingResult: null,
      logs: [],
      savedPath: null,
      createdAt: now,
      updatedAt: now,
    };
  },
};
