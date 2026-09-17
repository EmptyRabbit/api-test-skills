import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HomePanel from './HomePanel';
import { useSessionStore } from '../stores/session';

vi.mock('../api/client', () => ({
  ApiError: class ApiError extends Error {
    status = 500;
  },
  api: {
    get: vi.fn(async (path: string) => {
      if (path === '/api/platform') {
        return {
          models: [
            { name: 'glm-5.3', label: 'glm-5.3', default: true },
            { name: 'other', label: 'other' },
          ],
        };
      }
      throw new Error(path);
    }),
    post: vi.fn(),
  },
}));

vi.mock('../stores/chat', () => ({
  useChatStore: (sel: (s: { setQueued: (v: string) => void }) => unknown) =>
    sel({ setQueued: vi.fn() }),
}));

describe('HomePanel model picker', () => {
  beforeEach(() => {
    localStorage.clear();
    useSessionStore.setState({
      userName: 'alice',
      sessions: [],
      current: null,
      createSession: vi.fn(async (input) => {
        expect(input.model).toBe('other');
        expect(input.auth_token).toBe('from-ui');
        return {
          id: 's1',
          user_name: 'alice',
          git_url: input.git_url,
          base_branch: input.base_branch,
          feature_branch: input.feature_branch,
          title: 'x',
          status: 'ready',
          error: '',
          created_at: '',
        };
      }),
      openSession: vi.fn(async () => undefined),
    } as never);
  });

  it('loads yaml models and sends selected model plus ui token', async () => {
    render(<HomePanel />);
    const select = await screen.findByLabelText('模型');
    await waitFor(() => expect(select).toHaveValue('glm-5.3'));
    fireEvent.change(select, { target: { value: 'other' } });
    fireEvent.change(screen.getByLabelText('Auth Token'), { target: { value: 'from-ui' } });
    fireEvent.change(screen.getByPlaceholderText('GitLab 仓库 git 地址'), {
      target: { value: 'http://example.invalid/x.git' },
    });
    fireEvent.change(screen.getByPlaceholderText('对比分支 feature/…'), {
      target: { value: 'feat/x' },
    });
    fireEvent.change(screen.getByPlaceholderText(/描述要测的改动/), { target: { value: '测一下' } });
    fireEvent.click(screen.getByRole('button', { name: '开始' }));
    await waitFor(() => expect(useSessionStore.getState().createSession).toHaveBeenCalled());
  });

  it('requires username on start when yaml did not provide one', async () => {
    useSessionStore.setState({ userName: '' } as never);
    render(<HomePanel />);
    fireEvent.change(screen.getByPlaceholderText('GitLab 仓库 git 地址'), {
      target: { value: 'http://example.invalid/x.git' },
    });
    fireEvent.change(screen.getByPlaceholderText('对比分支 feature/…'), {
      target: { value: 'feat/x' },
    });
    fireEvent.change(screen.getByPlaceholderText(/先在右上角填写用户名/), {
      target: { value: '测一下' },
    });
    fireEvent.click(screen.getByRole('button', { name: '开始' }));
    expect(await screen.findByText('请填写用户名')).toBeInTheDocument();
    expect(useSessionStore.getState().createSession).not.toHaveBeenCalled();
  });
});
