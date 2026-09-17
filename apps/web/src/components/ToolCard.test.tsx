import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ToolCard, { processSummary, toolCommandLine, type ProcessStep } from './ToolCard';

const twoTools: ProcessStep[] = [
  { kind: 'tool', block: { kind: 'tool_use', id: 't1', name: 'Read', input: { file_path: 'a.yaml' } } },
  { kind: 'tool', block: { kind: 'tool_use', id: 't2', name: 'Grep', input: { pattern: 'x', path: '.' } } },
];

const twoDone = {
  steps: twoTools,
  results: [
    { kind: 'tool_result' as const, tool_use_id: 't1', content: 'file-body', is_error: false },
    { kind: 'tool_result' as const, tool_use_id: 't2', content: 'hit', is_error: false },
  ],
};

describe('ToolCard', () => {
  it('shows a running command line while waiting for the result', () => {
    render(
      <ToolCard
        steps={[
          { kind: 'tool', block: { kind: 'tool_use', id: 't1', name: 'Read', input: { file_path: 'D:/a.yaml' } } },
        ]}
        results={[]}
      />
    );
    expect(screen.getByText(/正在运行 Read D:\/a.yaml/)).toBeInTheDocument();
    expect(screen.queryByText(/D:\/a.yaml/, { selector: 'pre' })).toBeNull();
  });

  it('keeps the process collapsed until the summary is opened', () => {
    const { container } = render(<ToolCard {...twoDone} />);
    expect(screen.getByText('已运行 2 条命令')).toBeInTheDocument();
    expect(container.querySelector('details.tool-run')?.open).toBe(false);
    expect(screen.queryByText(/已运行 Read a.yaml/)).toBeNull();
    expect(screen.queryByText('file-body')).toBeNull();
  });

  it('lists each command collapsed; expanding one reveals its output', () => {
    const { container } = render(<ToolCard {...twoDone} />);

    fireEvent.click(screen.getByText('已运行 2 条命令'));
    expect(container.querySelector('details.tool-run')?.open).toBe(true);
    expect(screen.getByText(/已运行 Read a.yaml/)).toBeInTheDocument();
    expect(screen.getByText(/已运行 Grep x/)).toBeInTheDocument();
    expect(screen.queryByText('file-body')).toBeNull();

    fireEvent.click(screen.getByText(/已运行 Read a.yaml/));
    expect(screen.getByText('file-body')).toBeInTheDocument();
    expect(screen.queryByText('hit')).toBeNull();
  });

  it('folds thinking and tools into one collapsed block', () => {
    const { container } = render(
      <ToolCard
        steps={[
          { kind: 'thinking', text: '内部推理', key: 'h1' },
          ...twoTools,
        ]}
        results={twoDone.results}
      />
    );
    expect(screen.getByText('思考过程，已运行 2 条命令')).toBeInTheDocument();
    expect(container.querySelector('details.tool-run')?.open).toBe(false);
    expect(screen.queryByText('内部推理')).toBeNull();
    expect(screen.queryByText(/已运行 Read a.yaml/)).toBeNull();
  });
});

describe('processSummary', () => {
  it('shows 正在思考 when the live turn ends on thinking', () => {
    expect(
      processSummary([{ kind: 'thinking', text: '...', key: 'h1' }], [], true)
    ).toEqual({ running: true, text: '正在思考' });
  });
});

describe('toolCommandLine', () => {
  it('prefers file_path and command over raw json', () => {
    expect(
      toolCommandLine({ kind: 'tool_use', id: '1', name: 'Read', input: { file_path: 'x.ts' } })
    ).toBe('Read x.ts');
    expect(
      toolCommandLine({
        kind: 'tool_use',
        id: '2',
        name: 'Bash',
        input: { command: 'Get-Date' },
      })
    ).toBe('Get-Date');
  });
});
