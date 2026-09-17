import type { Block, ChatMessage } from '../types';

export function isSkillDumpText(text: string): boolean {
  return /^\s*Base directory for this skill:/m.test(text);
}

function pendingToolId(msg: ChatMessage): string | undefined {
  const uses = msg.blocks.filter((b): b is Extract<Block, { kind: 'tool_use' }> => b.kind === 'tool_use');
  const done = new Set(
    msg.blocks
      .filter((b): b is Extract<Block, { kind: 'tool_result' }> => b.kind === 'tool_result')
      .map((b) => b.tool_use_id)
  );
  return [...uses].reverse().find((u) => !done.has(u.id))?.id;
}

function lastSkillToolId(messages: ChatMessage[]): { index: number; id: string } | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role !== 'assistant') continue;
    const skill = [...m.blocks]
      .reverse()
      .find((b): b is Extract<Block, { kind: 'tool_use' }> => b.kind === 'tool_use' && b.name === 'Skill');
    if (skill) return { index: i, id: skill.id };
  }
  return null;
}

function toAssistantBlocks(blocks: Block[], toolUseId: string | undefined): Block[] {
  if (!toolUseId) return blocks;
  return blocks.map((b) =>
    b.kind === 'text'
      ? { kind: 'tool_result' as const, tool_use_id: toolUseId, content: b.text, is_error: false }
      : b
  );
}

function userPlainText(m: ChatMessage): string {
  return m.blocks
    .filter((b): b is Extract<Block, { kind: 'text' }> => b.kind === 'text')
    .map((b) => b.text)
    .join('\n');
}

/** 把 SDK 回推的 tool / Skill 正文并进上一条 assistant，避免当成对话气泡展开。 */
export function mergeToolResults(messages: ChatMessage[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  for (const m of messages) {
    const prev = out[out.length - 1];
    const pending = prev?.role === 'assistant' ? pendingToolId(prev) : undefined;
    const skillDump = m.role === 'user' && isSkillDumpText(userPlainText(m));
    const skillTarget = skillDump ? lastSkillToolId(out) : null;
    const isToolFollowup =
      m.role === 'user' &&
      (m.blocks.some((b) => b.kind === 'tool_result') || pending != null || skillTarget != null);
    if (skillDump && !skillTarget && pending == null) {
      continue;
    }
    if (isToolFollowup && (prev || skillTarget)) {
      const index = skillTarget?.index ?? out.length - 1;
      const toolId = skillTarget?.id ?? pending;
      const target = out[index];
      out[index] = {
        ...target,
        blocks: [...target.blocks, ...toAssistantBlocks(m.blocks, toolId)],
      };
    } else {
      out.push(m);
    }
  }
  return collapseAssistantTurns(out);
}

/** 同一轮里 SDK 会拆成多条 assistant，合并后工具才能收成「已运行 N 条命令」。 */
function collapseAssistantTurns(messages: ChatMessage[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  for (const m of messages) {
    const prev = out[out.length - 1];
    if (m.role === 'assistant' && prev?.role === 'assistant') {
      out[out.length - 1] = { ...prev, blocks: [...prev.blocks, ...m.blocks] };
    } else {
      out.push(m);
    }
  }
  return out;
}
