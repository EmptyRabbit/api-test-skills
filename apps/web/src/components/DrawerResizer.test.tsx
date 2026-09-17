import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import DrawerResizer from './DrawerResizer';

describe('DrawerResizer', () => {
  it('widens the drawer when dragged left', () => {
    const onChange = vi.fn();
    const onCommit = vi.fn();
    render(
      <DrawerResizer
        width={400}
        clamp={(w) => w}
        onChange={onChange}
        onCommit={onCommit}
      />
    );
    fireEvent.mouseDown(screen.getByRole('separator'), { clientX: 800, button: 0 });
    fireEvent.mouseMove(window, { clientX: 700 });
    expect(onChange).toHaveBeenCalledWith(500);
    fireEvent.mouseUp(window, { clientX: 700 });
    expect(onCommit).toHaveBeenCalledWith(500);
  });
});
