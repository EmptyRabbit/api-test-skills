export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail: unknown = message
  ) {
    super(message);
  }
}

function unpackDetail(data: unknown): { message: string; detail: unknown } {
  const raw =
    data && typeof data === 'object' && 'detail' in data
      ? (data as { detail: unknown }).detail
      : data;
  if (typeof raw === 'string') return { message: raw, detail: raw };
  if (raw == null) return { message: 'error', detail: raw };
  return { message: JSON.stringify(raw), detail: raw };
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(path, {
    method,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const raw = await resp.text();
  const parsed = parseBody(resp.status, raw, resp.headers.get('content-type'));
  if (!resp.ok) {
    const unpacked = unpackDetail(parsed === undefined ? raw : parsed);
    throw new ApiError(resp.status, unpacked.message, unpacked.detail);
  }
  if (resp.status === 204) return undefined as T;
  return parsed as T;
}

function parseBody(status: number, raw: string, contentType: string | null): unknown {
  const trimmed = raw.trim();
  if (!trimmed || status === 204) return undefined;
  if (trimmed.startsWith('<')) {
    throw new ApiError(
      status,
      '接口返回了网页而不是 JSON。请用 http://localhost:5173 打开前端（不要用 127.0.0.1:5173）',
      trimmed.slice(0, 80)
    );
  }
  const looksJson =
    (contentType || '').includes('json') || trimmed.startsWith('{') || trimmed.startsWith('[');
  if (!looksJson) {
    throw new ApiError(status, raw.slice(0, 120), raw);
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    throw new ApiError(status, '响应不是合法 JSON', raw.slice(0, 80));
  }
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
};
