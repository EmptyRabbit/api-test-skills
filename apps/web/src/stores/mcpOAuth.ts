import { create } from 'zustand';
import { ApiError, api } from '../api/client';

export type McpOAuthServer = {
  name: string;
  authorized: boolean;
  account?: string;
  cas_account?: string;
};

type DeviceFlow = {
  flow_id: string;
  server: string;
  user_code: string;
  verification_uri: string;
  verification_uri_complete: string;
  interval: number;
};

interface McpOAuthState {
  loaded: boolean;
  servers: McpOAuthServer[];
  flow: DeviceFlow | null;
  error: string;
  refresh: (userName: string) => Promise<void>;
  start: (userName: string, server: string) => Promise<void>;
  poll: (flowId: string) => Promise<'pending' | 'authorized' | 'mismatch' | 'error'>;
}

export function mcpOAuthReady(
  state: Pick<McpOAuthState, 'loaded' | 'servers'> & { error?: string }
): boolean {
  if (!state.loaded) return false;
  if (state.error && state.servers.length === 0) return false;
  return state.servers.every((s) => s.authorized);
}

export function isMcpOAuthRequiredError(e: unknown): boolean {
  if (!(e instanceof ApiError) || e.status !== 409 || typeof e.detail !== 'object' || e.detail === null) {
    return false;
  }
  return (e.detail as { code?: string }).code === 'mcp_oauth_required';
}

export const useMcpOAuthStore = create<McpOAuthState>((set) => ({
  loaded: false,
  servers: [],
  flow: null,
  error: '',

  refresh: async (userName) => {
    const name = userName.trim();
    if (!name) {
      set({ loaded: true, servers: [], flow: null, error: '' });
      return;
    }
    let lastError: unknown;
    for (let i = 0; i < 3; i++) {
      try {
        const data = await api.get<{ servers: McpOAuthServer[] }>(
          `/api/mcp-login/status?user_name=${encodeURIComponent(name)}`
        );
        set({ loaded: true, servers: data.servers, error: '' });
        return;
      } catch (e) {
        lastError = e;
        if (i < 2) await new Promise((r) => setTimeout(r, 400 * (i + 1)));
      }
    }
    set({
      loaded: true,
      error:
        lastError instanceof Error
          ? `无法检查 MCP 授权：${lastError.message}`
          : '无法检查 MCP 授权',
    });
  },

  start: async (userName, server) => {
    set({ error: '' });
    const started = await api.post<DeviceFlow>('/api/mcp-login/start', {
      user_name: userName.trim(),
      server,
    });
    set({ flow: started });
  },

  poll: async (flowId) => {
    const data = await api.get<{
      status: string;
      account?: string;
      cas_account?: string;
      user_name?: string;
      error?: string;
    }>(`/api/mcp-login/flows/${flowId}`);
    if (data.status === 'authorized') {
      set({ flow: null, error: '' });
      return 'authorized';
    }
    if (data.status === 'mismatch') {
      const account = data.account || data.cas_account || '';
      set({
        flow: null,
        error: `授权账号 ${account} 与用户名 ${data.user_name || ''} 不一致，请改侧栏用户名或重新授权`,
      });
      return 'mismatch';
    }
    if (data.status === 'error') {
      set({ flow: null, error: data.error || '授权失败' });
      return 'error';
    }
    return 'pending';
  },
}));
