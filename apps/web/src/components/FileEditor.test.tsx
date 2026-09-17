import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FileEditor from './FileEditor';
import { useFilesStore } from '../stores/files';
import { useSessionStore } from '../stores/session';

vi.mock('@monaco-editor/react', () => ({ default: () => <div data-testid="monaco" /> }));
vi.mock('./MarkdownWysiwyg', () => ({
  default: ({ value }: { value: string }) => <div className="md-wysiwyg">{value}</div>,
}));

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

describe('FileEditor markdown wysiwyg', () => {
  beforeEach(() => {
    useSessionStore.setState({ current: session });
    useFilesStore.setState({
      selected: 'artifacts/docs/00-context.md',
      openedContent: '# 很长\n\n' + '段落\n\n'.repeat(40),
      dirty: false,
    });
  });

  it('opens markdown in a scrollable wysiwyg surface', () => {
    const { container } = render(<FileEditor />);
    const wysiwyg = container.querySelector('.md-wysiwyg');
    expect(wysiwyg).toBeTruthy();
    expect(wysiwyg?.textContent).toContain('很长');
    expect(screen.queryByTestId('monaco')).toBeNull();
  });

  it('can switch to markdown source and back', () => {
    const { container } = render(<FileEditor />);
    fireEvent.click(screen.getByRole('button', { name: '源码' }));
    expect(container.querySelector('.md-wysiwyg')).toBeNull();
    expect(screen.getByTestId('monaco')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '所见即所得' }));
    expect(container.querySelector('.md-wysiwyg')).toBeTruthy();
  });

  it('uses monaco for non-markdown files', () => {
    useFilesStore.setState({
      selected: 'scripts/run.py',
      openedContent: 'print(1)\n',
      dirty: false,
    });
    render(<FileEditor />);
    expect(screen.getByTestId('monaco')).toBeTruthy();
    expect(screen.queryByRole('button', { name: '源码' })).toBeNull();
  });
});
