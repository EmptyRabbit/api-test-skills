import type { Block } from '../types';
import Collapsible from './Collapsible';
import { CopyBtn } from './ChatIcons';
import './MarkdownBody.css';

type ToolUse = Extract<Block, { kind: 'tool_use' }>;
type ToolResult = Extract<Block, { kind: 'tool_result' }>;

export type ProcessStep =
  | { kind: 'thinking'; text: string; key: string }
  | { kind: 'tool'; block: ToolUse };

function compactInput(input: Record<string, unknown>): string {
  try {
    return JSON.stringify(input);
  } catch {
    return '';
  }
}

export function toolCommandLine(block: ToolUse): string {
  const { name, input } = block;
  const path = String(input.file_path ?? input.path ?? input.target_file ?? '');
  if (name === 'Skill') return `Skill ${String(input.skill ?? '')}`.trim();
  if (name === 'Read') return `Read ${path || compactInput(input)}`.trim();
  if (name === 'Write' || name === 'Edit' || name === 'StrReplace') {
    return `${name} ${path || compactInput(input)}`.trim();
  }
  if (name === 'Bash' || name === 'Shell' || name === 'PowerShell') {
    return String(input.command ?? compactInput(input));
  }
  if (name === 'Grep') {
    return `Grep ${String(input.pattern ?? '')} ${path}`.trim();
  }
  const rest = compactInput(input);
  return rest ? `${name} ${rest}` : name;
}

function resultOf(block: ToolUse, results: ToolResult[]): ToolResult | undefined {
  return results.find((r) => r.tool_use_id === block.id);
}

export function processSummary(
  steps: ProcessStep[],
  results: ToolResult[],
  active = false
): { running: boolean; text: string } {
  const tools = steps.filter((s): s is Extract<ProcessStep, { kind: 'tool' }> => s.kind === 'tool');
  const thinkCount = steps.filter((s) => s.kind === 'thinking').length;
  const pending = tools.find((t) => !resultOf(t.block, results));
  if (pending) {
    return { running: true, text: `正在运行 ${toolCommandLine(pending.block)}` };
  }
  const last = steps[steps.length - 1];
  if (active && last?.kind === 'thinking') {
    return { running: true, text: '正在思考' };
  }
  const parts: string[] = [];
  if (thinkCount) parts.push(thinkCount === 1 ? '思考过程' : `${thinkCount} 段思考`);
  if (tools.length) parts.push(`已运行 ${tools.length} 条命令`);
  return { running: false, text: parts.join('，') || '思考过程' };
}

function ThinkItem({ text }: { text: string }) {
  return (
    <Collapsible
      className="tool-run-item"
      summary={<span className="tool-run-line">思考过程</span>}
    >
      <pre className="tool-run-args">{text}</pre>
    </Collapsible>
  );
}

function ToolItem({ block, result }: { block: ToolUse; result?: ToolResult }) {
  const line = toolCommandLine(block);
  const running = !result;
  return (
    <Collapsible
      className={`tool-run-item${result?.is_error ? ' err' : ''}`}
      summary={
        <span className={`tool-run-line${result?.is_error ? ' err' : ''}`}>
          {running ? '正在运行' : '已运行'} {line}
        </span>
      }
    >
      <pre className="tool-run-args">{JSON.stringify(block.input, null, 2)}</pre>
      {result ? (
        <div className="md-codeblock tool-run-out">
          <div className="md-codeblock-head">
            <span>text</span>
            <CopyBtn text={result.content} />
          </div>
          <pre className={result.is_error ? 'err-pre' : undefined}>{result.content.slice(0, 8000)}</pre>
        </div>
      ) : null}
    </Collapsible>
  );
}

export default function ToolCard({
  steps,
  results,
  active = false,
}: {
  steps: ProcessStep[];
  results: ToolResult[];
  active?: boolean;
}) {
  const { running, text } = processSummary(steps, results, active);
  const errored = results.some((r) => r.is_error);
  return (
    <Collapsible
      className={`tool-run${errored ? ' err' : ''}${running ? ' running' : ''}`}
      summary={
        <>
          {running ? <span className="tool-spin" aria-hidden /> : null}
          <span className="tool-run-summary">{text}</span>
        </>
      }
    >
      {steps.map((s) =>
        s.kind === 'thinking' ? (
          <ThinkItem key={s.key} text={s.text} />
        ) : (
          <ToolItem key={s.block.id} block={s.block} result={resultOf(s.block, results)} />
        )
      )}
    </Collapsible>
  );
}
