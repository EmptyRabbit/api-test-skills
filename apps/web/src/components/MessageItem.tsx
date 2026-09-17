import type { ReactNode } from 'react';
import MarkdownView from './MarkdownView';
import type { Block, ChatMessage } from '../types';
import { isSkillDumpText } from '../mergeChat';
import { stripOrchestrator } from '../orchestrator';
import { useChatStore } from '../stores/chat';
import ToolCard, { type ProcessStep } from './ToolCard';
import { ChatIconBtn, CopyBtn, PencilIcon } from './ChatIcons';

type ToolResult = Extract<Block, { kind: 'tool_result' }>;

function UserTurn({ text }: { text: string }) {
  const visible = stripOrchestrator(text);
  if (!visible.trim()) return null;
  return (
    <div className="turn-user">
      <div className="bubble-user">{visible}</div>
      <div className="turn-user-actions">
        <CopyBtn text={visible} />
        <ChatIconBtn label="编辑" onClick={() => useChatStore.getState().setComposerFill(visible)}>
          <PencilIcon />
        </ChatIconBtn>
      </div>
    </div>
  );
}

function AssistantBlocks({ blocks }: { blocks: Block[] }) {
  const live = useChatStore((s) => s.running);
  const toolResults = blocks.filter((b): b is ToolResult => b.kind === 'tool_result');
  const nodes: ReactNode[] = [];
  let i = 0;
  while (i < blocks.length) {
    const b = blocks[i];
    if (b.kind === 'tool_result') {
      i += 1;
      continue;
    }
    if (b.kind === 'thinking' || b.kind === 'tool_use') {
      const steps: ProcessStep[] = [];
      const start = i;
      while (i < blocks.length) {
        const x = blocks[i];
        if (x.kind === 'tool_result') {
          i += 1;
          continue;
        }
        if (x.kind === 'thinking') {
          steps.push({ kind: 'thinking', text: x.text, key: `h-${i}` });
          i += 1;
          continue;
        }
        if (x.kind === 'tool_use') {
          steps.push({ kind: 'tool', block: x });
          i += 1;
          continue;
        }
        break;
      }
      let peek = i;
      while (peek < blocks.length && blocks[peek].kind === 'tool_result') peek += 1;
      const active = live && peek >= blocks.length;
      const toolIds = new Set(steps.filter((s) => s.kind === 'tool').map((s) => s.block.id));
      nodes.push(
        <ToolCard
          key={`p-${start}`}
          steps={steps}
          results={toolResults.filter((r) => toolIds.has(r.tool_use_id))}
          active={active}
        />
      );
      continue;
    }
    if (b.kind === 'text' && !isSkillDumpText(b.text)) {
      nodes.push(<MarkdownView key={`t-${i}`}>{b.text}</MarkdownView>);
    }
    i += 1;
  }
  if (!nodes.length) return null;
  return <div className="asst">{nodes}</div>;
}

export default function MessageItem({ message }: { message: ChatMessage }) {
  if (message.role === 'result') return null;

  if (message.role === 'user') {
    const textBlock = message.blocks.find((b) => b.kind === 'text');
    if (!textBlock || isSkillDumpText(textBlock.text)) return null;
    return <UserTurn text={textBlock.text} />;
  }

  return <AssistantBlocks blocks={message.blocks} />;
}
