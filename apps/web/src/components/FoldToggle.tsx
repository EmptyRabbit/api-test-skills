type FoldToggleProps = {
  collapsed: boolean;
  collapseLabel: string;
  expandLabel: string;
  onClick: () => void;
  className?: string;
};

function Chevron({ dir }: { dir: 'left' | 'right' }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d={dir === 'left' ? 'M10 3.5 5.5 8 10 12.5' : 'M6 3.5 10.5 8 6 12.5'}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function FoldToggle({
  collapsed,
  collapseLabel,
  expandLabel,
  onClick,
  className,
}: FoldToggleProps) {
  const label = collapsed ? expandLabel : collapseLabel;
  return (
    <button
      type="button"
      className={className ? `fold-btn ${className}` : 'fold-btn'}
      title={label}
      aria-label={label}
      aria-expanded={!collapsed}
      onClick={onClick}
    >
      <Chevron dir={collapsed ? 'right' : 'left'} />
    </button>
  );
}
