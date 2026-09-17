import { useEffect, useRef } from 'react';

type DrawerResizerProps = {
  width: number;
  onChange: (width: number) => void;
  onCommit: (width: number) => void;
  clamp: (width: number) => number;
};

export default function DrawerResizer({ width, onChange, onCommit, clamp }: DrawerResizerProps) {
  const drag = useRef<{ startX: number; startW: number } | null>(null);
  const widthRef = useRef(width);
  const onChangeRef = useRef(onChange);
  const onCommitRef = useRef(onCommit);
  const clampRef = useRef(clamp);
  widthRef.current = width;
  onChangeRef.current = onChange;
  onCommitRef.current = onCommit;
  clampRef.current = clamp;

  useEffect(() => {
    function onMove(ev: MouseEvent) {
      if (!drag.current) return;
      onChangeRef.current(clampRef.current(drag.current.startW + drag.current.startX - ev.clientX));
    }
    function onUp(ev: MouseEvent) {
      if (!drag.current) return;
      const next = clampRef.current(drag.current.startW + drag.current.startX - ev.clientX);
      drag.current = null;
      document.body.classList.remove('drawer-resizing');
      onCommitRef.current(next);
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  return (
    <div
      className="drawer-resizer"
      role="separator"
      aria-orientation="vertical"
      aria-label="调整产物栏宽度"
      aria-valuenow={width}
      onMouseDown={(e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        drag.current = { startX: e.clientX, startW: widthRef.current };
        document.body.classList.add('drawer-resizing');
      }}
    />
  );
}
