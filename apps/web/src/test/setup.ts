import '@testing-library/jest-dom/vitest';

// @blocknote/mantine's MantineProvider calls window.matchMedia, which jsdom
// doesn't implement, to detect the system color scheme. Polyfill it so
// MarkdownWysiwyg (and anything else using BlockNote) can render under test.
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }) as MediaQueryList;
}
