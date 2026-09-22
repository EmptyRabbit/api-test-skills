import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSessionStore } from './session';

const fixtures = {
  s1: { id: 's1', status: 'ready', user_name: 'alice', title: 'repo-a', git_url: '', base_branch: 'master', feature_branch: 'feature/x', error: '', created_at: '' },
};

vi.mock('../api/client', () => ({
  api: {
    get: vi.fn(async (path: string) => {
      if (path.startsWith('/api/sessions/')) return fixtures.s1;
      if (path.startsWith('/api/sessions')) return [fixtures.s1];
      throw new Error(path);
    }),
    post: vi.fn(async () => ({ ...fixtures.s1, status: 'cloning' })),
    delete: vi.fn(async () => undefined),
  },
}));

import { api } from '../api/client';

describe('session store', () => {
  beforeEach(() => {
    localStorage.clear();
    useSessionStore.setState({
      userName: '',
      sessions: [],
      current: null,
    });
    vi.clearAllMocks();
  });

  it('setUserName persists to localStorage', () => {
    useSessionStore.getState().setUserName('alice');
    expect(localStorage.getItem('platform_user')).toBe('alice');
  });

  it('loadSessions filters by user', async () => {
    useSessionStore.setState({ userName: 'alice' });
    await useSessionStore.getState().loadSessions();
    expect(api.get).toHaveBeenCalledWith('/api/sessions?user_name=alice');
    expect(useSessionStore.getState().sessions).toHaveLength(1);
  });

  it('deleteSession purges and drops current', async () => {
    useSessionStore.setState({
      sessions: [fixtures.s1],
      current: fixtures.s1 as never,
    });
    await useSessionStore.getState().deleteSession('s1');
    expect(api.delete).toHaveBeenCalledWith('/api/sessions/s1?purge=true');
    expect(useSessionStore.getState().sessions).toEqual([]);
    expect(useSessionStore.getState().current).toBeNull();
  });
});
