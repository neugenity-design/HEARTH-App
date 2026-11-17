export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// Options can be strings or [stored value, displayed label] pairs.
export function dropdownOptions(options = [], value = '', blank = null) {
  const choices = blank == null ? options : [['', blank], ...options];
  return choices.map(option => {
    const [id, label] = Array.isArray(option) ? option : [option, option];
    return `<option value="${escapeHTML(id)}"${String(id) === String(value) ? ' selected' : ''}>${escapeHTML(label)}</option>`;
  }).join('');
}

export function dropdown({options = [], value = '', blank = null, attrs = {}} = {}) {
  const attributes = Object.entries(attrs).filter(([, v]) => v !== false && v != null).map(([key, v]) => v === true ? key : `${key}="${escapeHTML(v)}"`).join(' ');
  return `<select ${attributes}>${dropdownOptions(options, value, blank)}</select>`;
}

export function updateDropdown(select, options, {value = select.value, blank = null} = {}) {
  select.innerHTML = dropdownOptions(options, value, blank);
}
