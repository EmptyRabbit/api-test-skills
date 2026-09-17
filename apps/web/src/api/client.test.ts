import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from './client';

afterEach(() => vi.unstubAllGlobals());

describe('api client', () => {
  it('parses JSON response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('{"a":1}', { status: 200 }))
    );
    expect(await api.get('/x')).toEqual({ a: 1 });
  });

  it('throws ApiError with detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('{"detail":"nope"}', { status: 409 }))
    );
    await expect(api.post('/x', {})).rejects.toThrow(ApiError);
    await expect(api.post('/x', {})).rejects.toThrow('nope');
  });

  it('throws when response is HTML', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response('<!doctype html>', { status: 200, headers: { 'content-type': 'text/html' } })
      )
    );
    await expect(api.get('/x')).rejects.toThrow('接口返回了网页而不是 JSON');
  });

  it('keeps object detail on ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: { code: 'mcp_oauth_required', servers: ['q'] } }), {
            status: 409,
          })
      )
    );
    try {
      await api.post('/x', {});
      throw new Error('expected throw');
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).detail).toEqual({ code: 'mcp_oauth_required', servers: ['q'] });
    }
  });
});
