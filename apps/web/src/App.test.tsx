import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { useSessionStore } from './stores/session';

vi.mock('./api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('./components/HomePanel', () => ({
  default: () => <div>home</div>,
}));

vi.mock('./components/McpOAuthBar', () => ({
  default: () => null,
}));

vi.mock('./components/SessionSidebar', () => ({
  default: () => null,
}));

vi.mock('./components/ChatPanel', () => ({
  default: () => null,
}));

vi.mock('./components/FilePanel', () => ({
  default: () => null,
}));

vi.mock('./components/DrawerResizer', () => ({
  default: () => null,
}));

import { api } from './api/client';

describe('App username from platform.yaml', () => {
  beforeEach(() => {
    localStorage.clear();
    useSessionStore.setState({
      userName: '',
      sessions: [],
      current: null,
      loadSessions: vi.fn(async () => undefined),
    } as never);
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === '/api/platform') {
        return { models: [], user_name: 'zx.qiu' };
      }
      throw new Error(path);
    });
  });

  it('prefills header username from yaml when local value is empty', async () => {
    render(<App />);
    const input = screen.getByPlaceholderText('用户名（必填）');
    await waitFor(() => expect(input).toHaveValue('zx.qiu'));
    expect(useSessionStore.getState().userName).toBe('zx.qiu');
  });

  it('keeps a locally saved username instead of overwriting from yaml', async () => {
    useSessionStore.setState({ userName: 'local.user' } as never);
    render(<App />);
    expect(screen.getByPlaceholderText('用户名（必填）')).toHaveValue('local.user');
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/platform'));
    expect(screen.getByPlaceholderText('用户名（必填）')).toHaveValue('local.user');
    expect(useSessionStore.getState().userName).toBe('local.user');
  });
});
