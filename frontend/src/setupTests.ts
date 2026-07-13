import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrollIntoView / scrollTo
if (!window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = () => {};
}
