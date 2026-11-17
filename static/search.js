import {escapeHTML as escape} from './controls.js';
// One search control, matching policy, and input handler for pages and tables.
const handlers = new Map();
const timers = new WeakMap();

const normalize = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
function values(value) {
  if (value && typeof value === 'object') return Object.values(value).map(values).join(' ');
  return String(value ?? '');
}
export function matchesSearch(data, query) {
  const haystack = normalize(values(data));
  return normalize(query).split(' ').filter(Boolean).every(term => haystack.includes(term));
}
export function searchControl({scope, key, label, value = ''}) {
  return `<div class="search"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 21l-5-5M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14"/></svg><input type="search" aria-label="${escape(label)}" data-search-scope="${escape(scope)}" data-search-key="${escape(key)}" placeholder="${escape(label)}…" value="${escape(value)}"></div>`;
}
export function onSearch(scope, handler) { handlers.set(scope, handler); }
export function bindSearch(root) {
  root.addEventListener('input', event => {
    const input = event.target;
    if (!input.matches('[data-search-scope]')) return;
    clearTimeout(timers.get(input));
    timers.set(input, setTimeout(() => {
      if (input.isConnected) handlers.get(input.dataset.searchScope)?.(input.dataset.searchKey, input.value, input);
    }, 150));
  });
}
