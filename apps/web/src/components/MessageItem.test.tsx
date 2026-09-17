import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import MessageItem from './MessageItem';

describe('MessageItem', () => {
  it('renders assistant markdown text', () => {
    render(
      <MessageItem
        message={{ role: 'assistant', blocks: [{ kind: 'text', text: '# 标题' }] }}
      />
    );
    expect(screen.getByText('标题')).toBeInTheDocument();
  });

  it('renders thinking collapsed by default', () => {
    const { container } = render(
      <MessageItem
        message={{ role: 'assistant', blocks: [{ kind: 'thinking', text: '内部推理' }] }}
      />
    );
    const details = container.querySelector('details.think');
    expect(details).toBeTruthy();
    expect(details?.open).toBe(false);
    expect(screen.getByText('思考过程')).toBeInTheDocument();
    expect(screen.queryByText('内部推理')).toBeNull();
  });

  it('renders compact user bubble with copy and edit', () => {
    render(
      <MessageItem message={{ role: 'user', blocks: [{ kind: 'text', text: '梳理成 md' }] }} />
    );
    expect(screen.getByText('梳理成 md')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '复制' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '编辑' })).toBeInTheDocument();
  });

  it('hides skill dump bubbles', () => {
    const { container } = render(
      <MessageItem
        message={{
          role: 'user',
          blocks: [{ kind: 'text', text: 'Base directory for this skill: D:/x\n\n# 接口测试' }],
        }}
      />
    );
    expect(container.textContent).toBe('');
  });

  it('does not render Skill body until expanded', () => {
    const { container } = render(
      <MessageItem
        message={{
          role: 'assistant',
          blocks: [
            { kind: 'tool_use', id: 't1', name: 'Skill', input: { skill: 'generate-api-tests' } },
            {
              kind: 'tool_result',
              tool_use_id: 't1',
              content: 'Base directory for this skill: D:/secret\n\n# 接口测试',
              is_error: false,
            },
          ],
        }}
      />
    );
    const details = container.querySelector('details.tool');
    expect(details?.open).toBe(false);
    expect(screen.getByText(/Skill/)).toBeInTheDocument();
    expect(screen.queryByText(/D:\/secret/)).toBeNull();
  });

  it('does not render user tool_result as bubble', () => {
    const { container } = render(
      <MessageItem
        message={{
          role: 'user',
          blocks: [
            { kind: 'tool_result', tool_use_id: 't1', content: 'ok', is_error: false },
          ],
        }}
      />
    );
    expect(container.textContent).toBe('');
  });
});
