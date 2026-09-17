import type { SessionInfo } from './types';

type Status = SessionInfo['status'];

const STATUS_UI: Record<Status, { label: string; cls: string }> = {
  cloning: { label: '准备中', cls: 's-prep' },
  restoring: { label: '准备中', cls: 's-prep' },
  running: { label: '运行中', cls: 's-run' },
  error: { label: '失败', cls: 's-fail' },
  ready: { label: '就绪', cls: 's-ready' },
};

export function isPreparing(st: Status): boolean {
  return st === 'cloning' || st === 'restoring';
}

export function statusLabel(st: Status): string {
  return STATUS_UI[st].label;
}

export function statusClass(st: Status): string {
  return STATUS_UI[st].cls;
}

export function repoName(url: string): string {
  return url.replace(/\/$/, '').split('/').pop() || url;
}
