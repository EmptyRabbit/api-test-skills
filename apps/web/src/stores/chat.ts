import { message as antdMessage } from 'antd';
import { create } from 'zustand';
import { api } from '../api/client';
import { connectSessionEvents } from '../api/sse';
import type { Block, ChatMessage } from '../types';
import { isMcpOAuthRequiredError } from './mcpOAuth';

interface ChatState {
  messages: ChatMessage[];
  running: boolean;
  treeVersion: number;
  queued: string | null;
  setQueued: (text: string | null) => void;
  composerFill: string | null;
  setComposerFill: (text: string | null) => void;
  loadHistory: (sid: string) => Promise<void>;
  send: (sid: string, text: string) => Promise<void>;
  stop: (sid: string) => Promise<void>;
  attach: (sid: string) => () => void;
}

let detachFn: (() => void) | null = null;

/** SSE 会回推 chat 接口已发布的用户原文；与乐观插入相邻且内容相同则丢弃。 */
export function isDuplicateUserEcho(messages: ChatMessage[], incoming: ChatMessage): boolean {
  if (incoming.role !== 'user') return false;
  const last = messages[messages.length - 1];
  if (last?.role !== 'user') return false;
  return JSON.stringify(last.blocks) === JSON.stringify(incoming.blocks);
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  running: false,
  treeVersion: 0,
  queued: null,
  setQueued: (text) => set({ queued: text }),
  composerFill: null,
  setComposerFill: (text) => set({ composerFill: text }),

  loadHistory: async (sid) => {
    const rows = await api.get<{ id: number; role: ChatMessage['role']; blocks: Block[] }[]>(
      `/api/sessions/${sid}/messages`
    );
    set({ messages: rows });
  },

  send: async (sid, text) => {
    set((s) => ({
      messages: [...s.messages, { role: 'user', blocks: [{ kind: 'text', text }] }],
      running: true,
    }));
    try {
      await api.post(`/api/sessions/${sid}/chat`, { text });
    } catch (e) {
      const oauth = isMcpOAuthRequiredError(e);
      set((s) => ({
        messages: oauth ? s.messages.slice(0, -1) : s.messages,
        running: false,
        queued: oauth ? text : s.queued,
      }));
      if (!oauth) {
        antdMessage.error(`发送失败：${(e as Error).message}`);
      }
      throw e;
    }
  },

  stop: async (sid) => {
    await api.post(`/api/sessions/${sid}/stop`);
  },

  attach: (sid) => {
    const handlers = {
      onMessage: (ev: { role: string; blocks: unknown[] }) =>
        set((s) => {
          const next: ChatMessage = {
            role: ev.role as ChatMessage['role'],
            blocks: ev.blocks as Block[],
          };
          if (isDuplicateUserEcho(s.messages, next)) return s;
          return { messages: [...s.messages, next] };
        }),
      onDone: () => set((s) => ({ running: false, treeVersion: s.treeVersion + 1 })),
      onError: (ev: { message: string }) => {
        antdMessage.error(`agent 异常：${ev.message}`);
        set({ running: false });
      },
    };
    detachFn?.();
    detachFn = connectSessionEvents(sid, handlers);
    void get().loadHistory(sid);
    return () => {
      detachFn?.();
      detachFn = null;
    };
  },
}));
