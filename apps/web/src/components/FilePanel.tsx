import { useEffect, useState } from 'react';
import { useChatStore } from '../stores/chat';
import { useFilesStore } from '../stores/files';
import { useSessionStore } from '../stores/session';
import FileEditor from './FileEditor';
import FileTree from './FileTree';
import FoldToggle from './FoldToggle';
import VscodePanel from './VscodePanel';

export default function FilePanel() {
  const current = useSessionStore((s) => s.current);
  const treeVersion = useChatStore((s) => s.treeVersion);
  const reloadRoot = useFilesStore((s) => s.reloadRoot);
  const openFile = useFilesStore((s) => s.openFile);
  const [tab, setTab] = useState<'files' | 'vscode'>('files');
  const [treeCollapsed, setTreeCollapsed] = useState(false);
  const [nonce, setNonce] = useState(0);
  const sid = current?.id;

  useEffect(() => {
    if (!sid || treeVersion === 0) return;
    setNonce((n) => n + 1);
    void reloadRoot(sid);
  }, [treeVersion]);

  if (!current || !sid) return null;

  return (
    <div className="file-panel">
      <div className="file-tabs">
        <button className={`btn tiny ${tab === 'files' ? '' : 'ghost'}`} onClick={() => setTab('files')}>
          文件
        </button>
        <button className={`btn tiny ${tab === 'vscode' ? '' : 'ghost'}`} onClick={() => setTab('vscode')}>
          VS Code
        </button>
        <button
          className="btn ghost tiny ml-auto"
          onClick={() => {
            setNonce((n) => n + 1);
            void reloadRoot(sid);
          }}
        >
          刷新
        </button>
      </div>
      {tab === 'files' ? (
        <div className={`file-split${treeCollapsed ? ' tree-collapsed' : ''}`}>
          <div key={`tree-${sid}-${nonce}`} className="file-tree">
            <div className="file-tree-toolbar">
              <FoldToggle
                collapsed={treeCollapsed}
                collapseLabel="收起目录"
                expandLabel="展开目录"
                onClick={() => setTreeCollapsed((v) => !v)}
              />
            </div>
            <div className="file-tree-body">
              <FileTree onOpen={(p) => void openFile(sid, p)} />
            </div>
          </div>
          <div className="editor-pane">
            <FileEditor />
          </div>
        </div>
      ) : (
        <VscodePanel key={`${sid}-${nonce}`} reloadKey={nonce} />
      )}
    </div>
  );
}
