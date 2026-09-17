import { describe, expect, it } from 'vitest';
import type { ChatMessage } from '../types';
import { isDuplicateUserEcho } from './chat';

const userText = (text: string): ChatMessage => ({
  role: 'user',
  blocks: [{ kind: 'text', text }],
});

describe('isDuplicateUserEcho', () => {
  it('treats SSE user echo after optimistic insert as duplicate', () => {
    const messages = [userText('发布环境是fat8，appid正确，没有其他文档')];
    expect(isDuplicateUserEcho(messages, userText('发布环境是fat8，appid正确，没有其他文档'))).toBe(
      true
    );
  });

  it('keeps a different user message', () => {
    expect(isDuplicateUserEcho([userText('a')], userText('b'))).toBe(false);
  });

  it('keeps assistant messages', () => {
    const incoming: ChatMessage = { role: 'assistant', blocks: [{ kind: 'text', text: 'ok' }] };
    expect(isDuplicateUserEcho([userText('a')], incoming)).toBe(false);
  });

  it('keeps user tool_result after a text bubble', () => {
    const incoming: ChatMessage = {
      role: 'user',
      blocks: [{ kind: 'tool_result', tool_use_id: 't1', content: 'ok', is_error: false }],
    };
    expect(isDuplicateUserEcho([userText('a')], incoming)).toBe(false);
  });
});
