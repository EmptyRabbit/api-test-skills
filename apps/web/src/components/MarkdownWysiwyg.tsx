import { BlockNoteEditor } from '@blocknote/core';
import '@blocknote/core/fonts/inter.css';
import { BlockNoteView } from '@blocknote/mantine';
import '@blocknote/mantine/style.css';
import { useCreateBlockNote } from '@blocknote/react';
import type { KeyboardEvent } from 'react';
import { useEffect, useRef } from 'react';
import './MarkdownBody.css';
import './MarkdownWysiwyg.css';

type Props = {
  docKey: string;
  value: string;
  onChange: (markdown: string) => void;
  onSave?: () => void;
};

export default function MarkdownWysiwyg({ value, onChange, onSave }: Props) {
  const editor = useCreateBlockNote() as BlockNoteEditor;
  // Swallow the onChange fired by loading the initial content below, so
  // opening a file doesn't immediately mark it dirty. The caller remounts
  // this component (via `key={docKey}`) whenever the open file changes, so
  // this only needs to run once per mount.
  const isLoadingRef = useRef(true);

  useEffect(() => {
    const blocks = editor.tryParseMarkdownToBlocks(value);
    editor.replaceBlocks(editor.document, blocks);
    const id = window.setTimeout(() => {
      isLoadingRef.current = false;
    }, 0);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleChange() {
    if (isLoadingRef.current) return;
    onChange(editor.blocksToMarkdownLossy(editor.document));
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 's') return;
    event.preventDefault();
    onSave?.();
  }

  return (
    <div className="md-wysiwyg" onKeyDown={handleKeyDown}>
      <BlockNoteView editor={editor} onChange={handleChange} className="markdown-body" />
    </div>
  );
}
