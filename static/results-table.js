import {escapeHTML as escape} from './controls.js';
// Shared table behavior for lists, related records, reports, and drilldowns.
import {searchControl, matchesSearch, onSearch} from './search.js';
const sorts = new Map();
const queries = new Map();
const collator = new Intl.Collator('en', {numeric: true, sensitivity: 'base'});


export function compareValues(a, b, direction = 'asc') {
  const empty = value => value === '' || value == null || value === '—';
  if (empty(a) || empty(b)) return empty(a) === empty(b) ? 0 : empty(a) ? 1 : -1;
  const order = typeof a === 'number' && typeof b === 'number' ? a - b : collator.compare(String(a), String(b));
  return direction === 'desc' ? -order : order;
}

function cellValue(cell) {
  if (cell.dataset.sortType === 'number') return cell.dataset.sortValue === '' ? null : Number(cell.dataset.sortValue);
  if ('sortValue' in cell.dataset) return cell.dataset.sortValue;
  const copy = cell.cloneNode(true);
  copy.querySelectorAll('.sub').forEach(el => el.remove());
  const text = copy.textContent.trim();
  if (/^[+−-]?\$[\d,]+(?:\.\d+)?$/.test(text)) return Number(text.replace(/[$,+]/g, '').replace('−', '-'));
  if (/^[A-Z][a-z]{2} \d{1,2}, \d{4}$/.test(text)) return Date.parse(text);
  return text;
}

function applySort(table, sort) {
  const body = table.tBodies[0];
  if (!body) return;
  const rows = [...body.rows];
  rows.sort((a, b) => compareValues(cellValue(a.cells[sort.column]), cellValue(b.cells[sort.column]), sort.direction)
    || Number(a.dataset.originalOrder) - Number(b.dataset.originalOrder));
  body.append(...rows);
  [...table.tHead.rows[0].cells].forEach((header, column) => {
    const button = header.querySelector('[data-sort-column]');
    if (!button) return;
    const selected = column === sort.column;
    header.setAttribute('aria-sort', selected ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none');
    button.querySelector('.sort-indicator').textContent = selected ? (sort.direction === 'asc' ? '↑' : '↓') : '↕';
    button.setAttribute('aria-label', `Sort by ${button.dataset.title}, ${selected && sort.direction === 'asc' ? 'descending' : 'ascending'}`);
  });
}

function filterTable(wrapper, query) {
  const rows = [...wrapper.querySelectorAll('tbody tr')];
  let shown = 0;
  rows.forEach(row => {
    row.hidden = !matchesSearch([...row.cells].filter(cell => !cell.querySelector('.cell-actions')).map(cell => cell.textContent), query);
    if (!row.hidden) shown++;
  });
  const status = wrapper.querySelector('.results-count');
  if (status) status.textContent = query ? `${shown} of ${rows.length} records${shown ? '' : ' · No matching records'}` : `${rows.length} ${rows.length === 1 ? 'record' : 'records'}`;
}

export function resultsTable(headers, rows, key, {searchable = true} = {}) {
  const template = document.createElement('template');
  const query = queries.get(key) || '';
  template.innerHTML = `<div class="results-table">${searchable ? `<div class="results-tools">${searchControl({scope:'table',key,label:'Search '+headers[0].toLowerCase()+' results',value:query})}<span class="results-count" role="status" aria-live="polite"></span></div>` : ''}<div class="table-wrap"><table data-results-key="${escape(key)}"><thead><tr>${headers.map((h, index) => h ? `<th scope="col" aria-sort="none"><button type="button" class="sort-heading" data-sort-column="${index}" data-title="${escape(h)}" aria-label="Sort by ${escape(h)}, ascending">${escape(h)}<span class="sort-indicator" aria-hidden="true">↕</span></button></th>` : '<th scope="col"><span class="sr-only">Actions</span></th>').join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div></div>`;
  const table = template.content.querySelector('table');
  [...table.tBodies[0].rows].forEach((row, index) => row.dataset.originalOrder = index);
  if (sorts.has(key)) applySort(table, sorts.get(key));
  if (searchable) filterTable(template.content.querySelector('.results-table'), query);
  return template.innerHTML;
}

export function bindResultsTables(root) {
  onSearch('table', (key, query, input) => {
    queries.set(key, query);
    filterTable(input.closest('.results-table'), query);
  });
  root.addEventListener('click', event => {
    const button = event.target.closest('[data-sort-column]');
    if (!button) return;
    const table = button.closest('table');
    const key = table.dataset.resultsKey;
    const previous = sorts.get(key);
    const column = Number(button.dataset.sortColumn);
    const sort = {column, direction: previous?.column === column && previous.direction === 'asc' ? 'desc' : 'asc'};
    sorts.set(key, sort);
    applySort(table, sort);
  });
}
