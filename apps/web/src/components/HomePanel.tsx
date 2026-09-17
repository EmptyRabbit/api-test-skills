import { useEffect, useState } from 'react';
import { ApiError, api } from '../api/client';
import { composePrompt, type RepoRow } from '../orchestrator';
import { useChatStore } from '../stores/chat';
import { useSessionStore } from '../stores/session';

const EMPTY_REPO: RepoRow = { url: '', base: 'master', feat: '' };
const MODEL_KEY = 'platform_model';
const TOKEN_KEY = 'platform_auth_token';

export type PlatformModel = { name: string; label: string; default?: boolean };

export default function HomePanel() {
  const userName = useSessionStore((s) => s.userName);
  const createSession = useSessionStore((s) => s.createSession);
  const openSession = useSessionStore((s) => s.openSession);
  const setQueued = useChatStore((s) => s.setQueued);
  const [repos, setRepos] = useState<RepoRow[]>([{ ...EMPTY_REPO }]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [models, setModels] = useState<PlatformModel[]>([]);
  const [model, setModel] = useState(() => localStorage.getItem(MODEL_KEY) ?? '');
  const [authToken, setAuthToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? '');

  const valid = repos.filter((r) => r.url.trim() && r.feat.trim());
  const canStart = valid.length > 0 && !!draft.trim() && !busy;

  function resolvedUserName() {
    const el = document.getElementById('platform-user-name');
    return (el instanceof HTMLInputElement ? el.value : userName).trim();
  }

  useEffect(() => {
    void api.get<{ models: PlatformModel[] }>('/api/platform').then((body) => {
      const list = body.models || [];
      setModels(list);
      setModel((prev) => {
        if (prev && list.some((m) => m.name === prev)) return prev;
        return list.find((m) => m.default)?.name || list[0]?.name || '';
      });
    }).catch(() => {
      /* 后端未就绪时首页仍可填仓库，开始时再报错 */
    });
  }, []);

  function patchRepo(i: number, patch: Partial<RepoRow>) {
    setRepos((rows) => rows.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  }

  async function start() {
    if (!canStart) return;
    const name = resolvedUserName();
    if (!name) {
      setError('请填写用户名');
      return;
    }
    if (name !== userName) useSessionStore.getState().setUserName(name);
    setBusy(true);
    setError('');
    try {
      const first = valid[0];
      if (model) localStorage.setItem(MODEL_KEY, model);
      localStorage.setItem(TOKEN_KEY, authToken);
      const s = await createSession({
        git_url: first.url.trim(),
        base_branch: first.base.trim() || 'master',
        feature_branch: first.feat.trim(),
        ...(model ? { model } : {}),
        ...(authToken.trim() ? { auth_token: authToken.trim() } : {}),
      });
      setQueued(composePrompt(draft.trim(), valid));
      await openSession(s.id);
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      const down =
        e instanceof ApiError && e.status === 500 && (raw === '500' || /ECONNREFUSED/i.test(raw));
      setError(
        down
          ? '后端未启动（localhost:8000）。请先启动 uvicorn 或运行 apps/dev.cmd start，再点开始。'
          : raw
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="home">
      <div className="home-col">
        <div className="home-upper">
        <div className="home-hero">
          <h1>有什么想测的？</h1>
          <p className="sub">选好仓库、模型和对比分支，用一句话启动 agent</p>
        </div>
        <div className="launch-opts">
          <div className="launch-field">
            <label htmlFor="launch-model">模型</label>
            <select
              id="launch-model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={models.length === 0}
            >
              {models.length === 0 ? <option value="">未配置模型列表</option> : null}
              {models.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.label}
                  {m.default ? '（默认）' : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="launch-field">
            <label htmlFor="launch-token">Auth Token</label>
            <input
              id="launch-token"
              type="password"
              autoComplete="off"
              placeholder="留空则使用 platform.yaml 中的 token"
              value={authToken}
              onChange={(e) => setAuthToken(e.target.value)}
            />
          </div>
        </div>
        <div className="repos">
          <div className="repos-h">
            <strong>仓库与对比分支</strong>
            <span className="note">可加多个服务仓；工作区克隆第一个，其余写入首条任务</span>
            <button
              className="btn ghost tiny ml-auto"
              onClick={() => setRepos((rows) => [...rows, { ...EMPTY_REPO }])}
            >
              ＋ 仓库
            </button>
          </div>
          {repos.map((r, i) => (
            <div className="repo-row" key={i}>
              <input
                placeholder="GitLab 仓库 git 地址"
                value={r.url}
                onChange={(e) => patchRepo(i, { url: e.target.value })}
              />
              <input
                placeholder="base"
                value={r.base}
                onChange={(e) => patchRepo(i, { base: e.target.value })}
              />
              <input
                placeholder="对比分支 feature/…"
                value={r.feat}
                onChange={(e) => patchRepo(i, { feat: e.target.value })}
              />
              <button
                className="iconx"
                disabled={repos.length === 1}
                onClick={() => setRepos((rows) => rows.filter((_, j) => j !== i))}
              >
                ×
              </button>
            </div>
          ))}
        </div>
        </div>
        <div className="composer-wrap">
          <div className="composer">
            <textarea
              value={draft}
              placeholder={
                resolvedUserName()
                  ? '描述要测的改动，例如：分析这两个仓 feature 分支对创单的影响（将走 api-generate-api-tests）'
                  : '先在右上角填写用户名'
              }
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void start();
                }
              }}
            />
            <div className="composer-foot">
              <span className="hint">Enter 发送 · Shift+Enter 换行</span>
              <button className="btn" disabled={!canStart} onClick={() => void start()}>
                {busy ? '准备中…' : '开始'}
              </button>
            </div>
          </div>
          {error ? <p className="note" style={{ color: 'var(--danger)', marginTop: 10 }}>{error}</p> : null}
        </div>
      </div>
    </div>
  );
}
