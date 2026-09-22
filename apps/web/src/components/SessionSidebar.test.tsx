import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSessionStore } from '../stores/session';
import SessionSidebar from './SessionSidebar';

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

vi.mock('antd', () => ({
  message: { error: vi.fn() },
}));

const session = {
  id: 's1',
  user_name: 'alice',
  git_url: 'http://example.invalid/marketing-reach.git',
  base_branch: 'master',
  feature_branch: 'feat/x',
  title: 'marketing-reach-algorithm-recommendation-service',
  status: 'ready',
  error: '',
  created_at: '',
};

describe('SessionSidebar delete', () => {
  beforeEach(() => {
    useSessionStore.setState({
      userName: 'alice',
      sessions: [session],
      current: null,
      openSession: vi.fn(async () => undefined),
      deleteSession: vi.fn(async () => undefined),
      clearCurrent: vi.fn(),
    } as never);
    vi.stubGlobal('confirm', vi.fn(() => true));
  });

  it('shows a delete icon and purges after confirm', async () => {
    render(<SessionSidebar collapsed={false} onToggle={() => undefined} />);
    fireEvent.click(screen.getByRole('button', { name: '删除会话' }));
    await waitFor(() => expect(useSessionStore.getState().deleteSession).toHaveBeenCalledWith('s1'));
    expect(useSessionStore.getState().openSession).not.toHaveBeenCalled();
  });

  it('does not delete when confirm is cancelled', async () => {
    vi.stubGlobal('confirm', vi.fn(() => false));
    render(<SessionSidebar collapsed={false} onToggle={() => undefined} />);
    fireEvent.click(screen.getByRole('button', { name: '删除会话' }));
    expect(useSessionStore.getState().deleteSession).not.toHaveBeenCalled();
  });
});
