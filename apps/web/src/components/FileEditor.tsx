import Editor from '@monaco-editor/react';
import { useEffect, useState } from 'react';
import { useFilesStore } from '../stores/files';
import { useSessionStore } from '../stores/session';
import MarkdownWysiwyg from './MarkdownWysiwyg';

function langOf(path: string): string {
  if (path.endsWith('.py')) return 'python';
  if (path.endsWith('.md')) return 'markdown';
  if (path.endsWith('.yaml') || path.endsWith('.yml')) return 'yaml';
  if (path.endsWith('.json')) return 'json';
  return 'plaintext';
}

export default function FileEditor() {
  const current = useSessionStore((s) => s.current);
  const { selected, openedContent, dirty, setContent, saveFile } = useFilesStore();
  const [sourceMode, setSourceMode] = useState(false);
  const isMd = !!selected?.endsWith('.md');

  useEffect(() => {
    setSourceMode(false);
  }, [selected]);

  if (!current || !selected || openedContent === null) {
    return <div className="empty">选择一个文件查看</div>;
  }

  const save = () => void saveFile(current.id);

  return (
    <>
      <div className="editor-bar">
        <span className="path">{selected}</span>
        {dirty && <span className="dirty">未保存</span>}
        {isMd && (
          <button className="btn ghost tiny" onClick={() => setSourceMode((v) => !v)}>
            {sourceMode ? '所见即所得' : '源码'}
          </button>
        )}
        <button className="btn tiny" disabled={!dirty} onClick={save}>
          保存
        </button>
      </div>
      <div className="editor-body">
        {isMd && !sourceMode ? (
          <MarkdownWysiwyg key={selected} docKey={selected} value={openedContent} onChange={setContent} onSave={save} />
        ) : (
          <Editor
            height="100%"
            language={langOf(selected)}
            value={openedContent}
            onChange={(v) => setContent(v ?? '')}
            options={{ minimap: { enabled: false }, wordWrap: 'on', fontSize: 14 }}
            onMount={(editor, monaco) => {
              editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, save);
            }}
          />
        )}
      </div>
    </>
  );
}
