import type { Block } from '../types';
import Collapsible from './Collapsible';

type ToolUse = Extract<Block, { kind: 'tool_use' }>;
type ToolResult = Extract<Block, { kind: 'tool_result' }>;

export default function ToolCard({ block, results }: { block: ToolUse; results: ToolResult[] }) {
  const summary =
    block.name === 'Skill' ? String(block.input.skill ?? '') : JSON.stringify(block.input).slice(0, 120);
  const errored = results.some((r) => r.is_error);
  return (
    <Collapsible
      className="tool"
      summary={
        <>
          <span className={`chip ${errored ? 'err' : ''}`}>{block.name}</span>
          {summary}
        </>
      }
    >
      <pre>{JSON.stringify(block.input, null, 2)}</pre>
      {results.map((r, i) => (
        <pre key={i} className={r.is_error ? 'err-pre' : undefined}>
          {r.content.slice(0, 2000)}
        </pre>
      ))}
    </Collapsible>
  );
}
