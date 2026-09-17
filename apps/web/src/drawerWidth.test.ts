import { beforeEach, describe, expect, it } from 'vitest';
import {
  clampDrawerWidth,
  defaultDrawerWidth,
  DRAWER_W_KEY,
  DRAWER_W_MIN,
  readDrawerWidth,
  SIDEBAR_COLLAPSED_W,
  SIDEBAR_W,
  writeDrawerWidth,
} from './drawerWidth';

describe('clampDrawerWidth', () => {
  it('clamps below min', () => {
    expect(clampDrawerWidth(10, 1400)).toBe(DRAWER_W_MIN);
  });

  it('leaves room for sidebar and chat', () => {
    expect(clampDrawerWidth(2000, 1000)).toBe(1000 - SIDEBAR_W - 320);
  });

  it('uses collapsed sidebar when computing max', () => {
    expect(clampDrawerWidth(2000, 1000, SIDEBAR_COLLAPSED_W)).toBe(1000 - SIDEBAR_COLLAPSED_W - 320);
  });
});

describe('drawer width persistence', () => {
  beforeEach(() => {
    localStorage.clear();
    Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 1600 });
  });

  it('defaults to half of the main pane', () => {
    expect(readDrawerWidth()).toBe(defaultDrawerWidth(1600, SIDEBAR_W));
    expect(readDrawerWidth()).toBe((1600 - SIDEBAR_W) / 2);
  });

  it('treats the old 520 default as unset', () => {
    localStorage.setItem(DRAWER_W_KEY, '520');
    expect(readDrawerWidth()).toBe(defaultDrawerWidth(1600, SIDEBAR_W));
  });

  it('round-trips a stored width', () => {
    writeDrawerWidth(400);
    expect(localStorage.getItem(DRAWER_W_KEY)).toBe('400');
    expect(readDrawerWidth()).toBe(400);
  });
});
