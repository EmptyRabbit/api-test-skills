import { describe, expect, it } from 'vitest';
import { ORCHESTRATOR, composePrompt, stripOrchestrator } from './orchestrator';

describe('orchestrator prompt', () => {
  it('prepends the internal instruction for the agent', () => {
    const sent = composePrompt('Pod IP: 1.1.1.1', [{ url: 'git@x', base: 'master', feat: 'feat' }]);
    expect(sent.startsWith(ORCHESTRATOR)).toBe(true);
    expect(sent).toContain('Pod IP: 1.1.1.1');
  });

  it('hides the internal instruction in the bubble', () => {
    const sent = composePrompt('Pod IP: 1.1.1.1\n测试接口: api/x', [
      { url: 'git@x', base: 'master', feat: 'feat' },
    ]);
    expect(stripOrchestrator(sent)).toBe('Pod IP: 1.1.1.1\n测试接口: api/x');
  });
});
