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
    const details = container.querySelector('details.tool-run');
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

  it('folds thinking and tools into one collapsed process, leaving the answer visible', () => {
    render(
      <MessageItem
        message={{
          role: 'assistant',
          blocks: [
            { kind: 'thinking', text: '内部推理' },
            { kind: 'tool_use', id: 't1', name: 'Read', input: { file_path: 'a.yaml' } },
            { kind: 'tool_result', tool_use_id: 't1', content: 'ok', is_error: false },
            { kind: 'text', text: '工具调用成功。' },
          ],
        }}
      />
    );
    expect(screen.getByText('思考过程，已运行 1 条命令')).toBeInTheDocument();
    expect(screen.getByText('工具调用成功。')).toBeInTheDocument();
    expect(screen.queryByText('内部推理')).toBeNull();
    expect(screen.queryByText('ok')).toBeNull();
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
            { kind: 'tool_use', id: 't1', name: 'Skill', input: { skill: 'api-generate-api-tests' } },
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
    const details = container.querySelector('details.tool-run');
    expect(details?.open).toBe(false);
    expect(screen.getByText('已运行 1 条命令')).toBeInTheDocument();
    expect(screen.queryByText(/D:\/secret/)).toBeNull();
  });

  it('hides the internal orchestrator line in the user bubble', () => {
    render(
      <MessageItem
        message={{
          role: 'user',
          blocks: [
            {
              kind: 'text',
              text: '用 api-generate-api-tests 为本任务生成接口测试用例，必须走该主编排，不要自行写用例。\n\nPod IP: 10.1.1.1',
            },
          ],
        }}
      />
    );
    expect(screen.queryByText(/必须走该主编排/)).toBeNull();
    expect(screen.getByText(/Pod IP: 10.1.1.1/)).toBeInTheDocument();
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
