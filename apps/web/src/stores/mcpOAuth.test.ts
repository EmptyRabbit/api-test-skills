import { describe, expect, it } from 'vitest';
import { ApiError } from '../api/client';
import { isMcpOAuthRequiredError, mcpOAuthReady } from './mcpOAuth';

describe('mcpOAuthReady', () => {
  it('waits until status is loaded', () => {
    expect(mcpOAuthReady({ loaded: false, servers: [] })).toBe(false);
  });

  it('allows chat when there is no oauth mcp', () => {
    expect(mcpOAuthReady({ loaded: true, servers: [] })).toBe(true);
  });

  it('blocks chat when status check failed with no servers', () => {
    expect(mcpOAuthReady({ loaded: true, servers: [], error: '无法检查 MCP 授权' })).toBe(false);
  });

  it('blocks chat until every oauth mcp is authorized', () => {
    expect(
      mcpOAuthReady({
        loaded: true,
        servers: [{ name: 'oauth-mcp', authorized: false, account: '' }],
      })
    ).toBe(false);
    expect(
      mcpOAuthReady({
        loaded: true,
        servers: [{ name: 'oauth-mcp', authorized: true, account: 'alice' }],
      })
    ).toBe(true);
  });
});

describe('isMcpOAuthRequiredError', () => {
  it('matches structured 409 oauth detail', () => {
    expect(
      isMcpOAuthRequiredError(
        new ApiError(409, 'mcp_oauth_required', { code: 'mcp_oauth_required', servers: ['q'] })
      )
    ).toBe(true);
  });

  it('ignores other 409s', () => {
    expect(isMcpOAuthRequiredError(new ApiError(409, 'agent is running'))).toBe(false);
  });
});
