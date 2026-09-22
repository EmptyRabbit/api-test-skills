import { create } from 'zustand';
import { api } from '../api/client';
import { isPreparing } from '../status';
import type { SessionInfo } from '../types';

interface SessionState {
  userName: string;
  sessions: SessionInfo[];
  current: SessionInfo | null;
  setUserName: (name: string) => void;
  loadSessions: () => Promise<void>;
  createSession: (input: {
    git_url: string;
    base_branch: string;
    feature_branch: string;
    model?: string;
    auth_token?: string;
  }) => Promise<SessionInfo>;
  openSession: (sid: string) => Promise<void>;
  deleteSession: (sid: string) => Promise<void>;
  clearCurrent: () => void;
}

async function pollUntilDone(sid: string, onEach: (s: SessionInfo) => void) {
  for (;;) {
    const s = await api.get<SessionInfo>(`/api/sessions/${sid}`);
    onEach(s);
    if (!isPreparing(s.status)) return;
    await new Promise((r) => setTimeout(r, 2000));
  }
}

export const useSessionStore = create<SessionState>((set, get) => ({
  userName: localStorage.getItem('platform_user') ?? '',
  sessions: [],
  current: null,

  setUserName: (name) => {
    localStorage.setItem('platform_user', name);
    set({ userName: name });
  },

  loadSessions: async () => {
    const name = get().userName;
    const qs = name ? `?user_name=${encodeURIComponent(name)}` : '';
    const sessions = await api.get<SessionInfo[]>(`/api/sessions${qs}`);
    set({ sessions });
  },

  createSession: async (input) => {
    const s = await api.post<SessionInfo>('/api/sessions', {
      user_name: get().userName,
      ...input,
    });
    set({ sessions: [s, ...get().sessions] });
    return s;
  },

  openSession: async (sid) => {
    const s = await api.get<SessionInfo>(`/api/sessions/${sid}`);
    set({ current: s });
    if (isPreparing(s.status)) {
      await pollUntilDone(sid, (each) => set({ current: each }));
    }
  },

  deleteSession: async (sid) => {
    await api.delete(`/api/sessions/${sid}?purge=true`);
    const { current, sessions } = get();
    set({
      sessions: sessions.filter((s) => s.id !== sid),
      current: current?.id === sid ? null : current,
    });
  },

  clearCurrent: () => set({ current: null }),
}));
