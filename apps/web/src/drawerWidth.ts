export const DRAWER_W_KEY = 'platform_drawer_width';
export const DRAWER_W_MIN = 280;
export const SIDEBAR_W = 260;
export const SIDEBAR_COLLAPSED_W = 48;
const CHAT_MIN_W = 320;

function viewportWidth(): number {
  return typeof window === 'undefined' ? 1280 : window.innerWidth;
}

export function sidebarWidth(collapsed: boolean): number {
  return collapsed ? SIDEBAR_COLLAPSED_W : SIDEBAR_W;
}

export function defaultDrawerWidth(viewport = viewportWidth(), sidebarW = SIDEBAR_W): number {
  return clampDrawerWidth((viewport - sidebarW) / 2, viewport, sidebarW);
}

export function clampDrawerWidth(
  width: number,
  viewport = viewportWidth(),
  sidebarW = SIDEBAR_W,
): number {
  const max = Math.max(DRAWER_W_MIN, viewport - sidebarW - CHAT_MIN_W);
  if (!Number.isFinite(width)) return Math.min(defaultDrawerWidth(viewport, sidebarW), max);
  return Math.round(Math.min(max, Math.max(DRAWER_W_MIN, width)));
}

export function readDrawerWidth(sidebarW = SIDEBAR_W): number {
  try {
    const raw = localStorage.getItem(DRAWER_W_KEY);
    const n = raw == null ? NaN : Number(raw);
    // 旧默认 520 视为未设置，改走对半分。
    if (!Number.isFinite(n) || n === 520) return defaultDrawerWidth(viewportWidth(), sidebarW);
    return clampDrawerWidth(n, viewportWidth(), sidebarW);
  } catch {
    return defaultDrawerWidth(viewportWidth(), sidebarW);
  }
}

export function writeDrawerWidth(width: number, sidebarW = SIDEBAR_W): void {
  try {
    localStorage.setItem(DRAWER_W_KEY, String(clampDrawerWidth(width, viewportWidth(), sidebarW)));
  } catch {
    /* ignore quota / private mode */
  }
}
