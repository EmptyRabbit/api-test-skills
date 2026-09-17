import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FilePanel from './FilePanel';
import { useChatStore } from '../stores/chat';
import { useFilesStore } from '../stores/files';
import { useSessionStore } from '../stores/session';

vi.mock('./FileTree', () => ({ default: () => <div data-testid="file-tree" /> }));
vi.mock('./FileEditor', () => ({ default: () => <div data-testid="file-editor" /> }));
vi.mock('./VscodePanel', () => ({ default: () => <div data-testid="vscode" /> }));

const session = {
  id: 's1',
  user_name: 'alice',
  git_url: 'http://example.invalid/x.git',
  base_branch: 'master',
  feature_branch: 'feature/x',
  title: 'x',
  status: 'ready' as const,
  error: '',
  created_at: '',
};

describe('FilePanel refresh icon', () => {
  const reloadRoot = vi.fn(async () => undefined);

  beforeEach(() => {
    reloadRoot.mockClear();
    useSessionStore.setState({ current: session });
    useChatStore.setState({ treeVersion: 0 });
    useFilesStore.setState({ reloadRoot, openFile: vi.fn(async () => undefined) } as never);
  });

  it('puts a refresh icon in the tree toolbar instead of the tab bar', () => {
    const { container } = render(<FilePanel onClose={() => undefined} />);
    const refresh = screen.getByRole('button', { name: '刷新' });
    expect(container.querySelector('.file-tabs')?.contains(refresh)).toBe(false);
    expect(container.querySelector('.file-tree-toolbar')?.contains(refresh)).toBe(true);
    fireEvent.click(refresh);
    expect(reloadRoot).toHaveBeenCalledWith('s1');
  });
});
