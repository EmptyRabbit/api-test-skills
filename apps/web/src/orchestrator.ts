export const ORCHESTRATOR =
  '用 api-generate-api-tests 为本任务生成接口测试用例，必须走该主编排，不要自行写用例。';

export type RepoRow = { url: string; base: string; feat: string };

/** 发给 agent 时拼上内部主编排指令；对话里不展示这段。 */
export function composePrompt(text: string, repos: RepoRow[]): string {
  const body = text.startsWith(ORCHESTRATOR) ? text : `${ORCHESTRATOR}\n\n${text}`;
  if (repos.length <= 1) return body;
  const lines = repos.map((r) => `- ${r.url}  ${r.base} → ${r.feat}`);
  return `对比仓库（工作区克隆第一个，其余请按 GitLab 地址分析）：\n${lines.join('\n')}\n\n${body}`;
}

export function stripOrchestrator(text: string): string {
  const trimmed = text.trimStart();
  if (!trimmed.startsWith(ORCHESTRATOR)) return text;
  return trimmed.slice(ORCHESTRATOR.length).replace(/^\s*\n+/, '');
}
