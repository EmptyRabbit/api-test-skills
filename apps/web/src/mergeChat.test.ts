import { describe, expect, it } from 'vitest';
import { mergeToolResults } from './mergeChat';
import type { ChatMessage } from './types';

describe('mergeToolResults', () => {
  it('folds skill text into the Skill card instead of a user bubble', () => {
    const messages: ChatMessage[] = [
      {
        role: 'assistant',
        blocks: [{ kind: 'tool_use', id: 't1', name: 'Skill', input: { skill: 'generate-api-tests' } }],
      },
      {
        role: 'user',
        blocks: [{ kind: 'text', text: 'Base directory for this skill: D:/x\n\n# 接口测试' }],
      },
    ];
    const out = mergeToolResults(messages);
    expect(out).toHaveLength(1);
    expect(out[0].role).toBe('assistant');
    const result = out[0].blocks.find((b) => b.kind === 'tool_result');
    expect(result).toMatchObject({ kind: 'tool_result', tool_use_id: 't1' });
  });

  it('keeps the next real user message as a bubble', () => {
    const messages: ChatMessage[] = [
      {
        role: 'assistant',
        blocks: [
          { kind: 'tool_use', id: 't1', name: 'Skill', input: {} },
          { kind: 'tool_result', tool_use_id: 't1', content: 'ok', is_error: false },
          { kind: 'text', text: '已写入' },
        ],
      },
      { role: 'user', blocks: [{ kind: 'text', text: '可以' }] },
    ];
    const out = mergeToolResults(messages);
    expect(out).toHaveLength(2);
    expect(out[1].blocks[0]).toMatchObject({ kind: 'text', text: '可以' });
  });

  it('folds skill dump even after the Skill tool already has a result', () => {
    const messages: ChatMessage[] = [
      {
        role: 'assistant',
        blocks: [
          { kind: 'tool_use', id: 't1', name: 'Skill', input: { skill: 'generate-api-tests' } },
          { kind: 'tool_result', tool_use_id: 't1', content: 'ok', is_error: false },
        ],
      },
      {
        role: 'user',
        blocks: [{ kind: 'text', text: 'Base directory for this skill: D:/x\n\n# 接口测试' }],
      },
    ];
    const out = mergeToolResults(messages);
    expect(out).toHaveLength(1);
    expect(out[0].role).toBe('assistant');
  });
});
