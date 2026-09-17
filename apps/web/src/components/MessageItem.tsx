import MarkdownView from './MarkdownView';
import type { ChatMessage } from '../types';
import { isSkillDumpText } from '../mergeChat';
import { useChatStore } from '../stores/chat';
import Collapsible from './Collapsible';
import ToolCard from './ToolCard';
import { ChatIconBtn, CopyBtn, PencilIcon } from './ChatIcons';

function UserTurn({ text }: { text: string }) {
  return (
    <div className="turn-user">
      <div className="bubble-user">{text}</div>
      <div className="turn-user-actions">
        <CopyBtn text={text} />
        <ChatIconBtn label="编辑" onClick={() => useChatStore.getState().setComposerFill(text)}>
          <PencilIcon />
        </ChatIconBtn>
      </div>
    </div>
  );
}

export default function MessageItem({ message }: { message: ChatMessage }) {
  if (message.role === 'result') return null;

  if (message.role === 'user') {
    const textBlock = message.blocks.find((b) => b.kind === 'text');
    if (!textBlock || isSkillDumpText(textBlock.text)) return null;
    return <UserTurn text={textBlock.text} />;
  }

  const toolResults = message.blocks.filter(
    (b): b is Extract<typeof b, { kind: 'tool_result' }> => b.kind === 'tool_result'
  );

  return (
    <div className="asst">
      {message.blocks.map((b, i) => {
        switch (b.kind) {
          case 'text':
            if (isSkillDumpText(b.text)) return null;
            return <MarkdownView key={i}>{b.text}</MarkdownView>;
          case 'thinking':
            return (
              <Collapsible key={i} className="think" summary="思考过程">
                <pre>{b.text}</pre>
              </Collapsible>
            );
          case 'tool_use':
            return (
              <ToolCard
                key={b.id}
                block={b}
                results={toolResults.filter((r) => r.tool_use_id === b.id)}
              />
            );
          default:
            return null;
        }
      })}
    </div>
  );
}
