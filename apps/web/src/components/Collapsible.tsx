import { useState, type MouseEvent, type ReactNode } from 'react';

export default function Collapsible({
  className,
  summary,
  children,
}: {
  className: string;
  summary: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  function toggle(e: MouseEvent<HTMLElement>) {
    e.preventDefault();
    setOpen((v) => !v);
  }

  return (
    <details className={className} open={open}>
      <summary onClick={toggle}>{summary}</summary>
      {open ? children : null}
    </details>
  );
}
