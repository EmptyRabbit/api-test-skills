import { useState, type ReactNode } from 'react';

type ChatIconBtnProps = {
  label: string;
  onClick: () => void;
  children: ReactNode;
};

export function ChatIconBtn({ label, onClick, children }: ChatIconBtnProps) {
  return (
    <button type="button" className="chat-icon-btn" aria-label={label} title={label} onClick={onClick}>
      {children}
    </button>
  );
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 13l4 4L19 7" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="9" y="9" width="11" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

export function CopyBtn({ text }: { text: string }) {
  const [done, setDone] = useState(false);

  function copy() {
    void navigator.clipboard.writeText(text).then(() => {
      setDone(true);
      window.setTimeout(() => setDone(false), 1200);
    });
  }

  return (
    <ChatIconBtn label={done ? '已复制' : '复制'} onClick={copy}>
      {done ? <CheckIcon /> : <CopyIcon />}
    </ChatIconBtn>
  );
}

export function PencilIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
    </svg>
  );
}
