'use strict';
function setupCatalogueSearch(root = document) {
  root.querySelectorAll('select[data-catalogue]:not([data-ready])').forEach(select => {
    select.dataset.ready = 'true';
    const input = document.createElement('input');
    input.type = 'search';
    input.placeholder = `Search ESCO ${select.dataset.catalogue}s…`;
    input.setAttribute('aria-label', `Search for an ESCO ${select.dataset.catalogue}`);
    input.style.marginBottom = '8px';
    select.before(input);
    const status = document.createElement('small');
    status.className = 'helptext';
    status.setAttribute('aria-live', 'polite');
    status.textContent = 'Type at least 2 characters, then choose a result below.';
    select.after(status);
    let timer, controller;
    input.addEventListener('input', () => {
      clearTimeout(timer);
      controller?.abort();
      if (input.value.trim().length < 2) return;
      timer = setTimeout(async () => {
        controller = new AbortController();
        try {
          status.textContent = 'Searching…';
          const params = new URLSearchParams({q: input.value.trim(), kind: select.dataset.catalogue});
          const response = await fetch(`/catalogue/search/?${params}`, {signal: controller.signal});
          if (!response.ok) throw new Error('Search unavailable');
          const data = await response.json();
          const selected = select.selectedOptions[0];
          const selectedValue = select.value;
          const selectedLabel = selected?.textContent;
          select.replaceChildren(new Option('Choose a search result', ''));
          if (selectedValue && !data.results.some(item => String(item.id) === selectedValue)) {
            select.add(new Option(selectedLabel, selectedValue));
          }
          data.results.forEach(item => select.add(new Option(item.label, item.id)));
          select.value = selectedValue;
          status.textContent = data.results.length ? `${data.results.length} results. Choose a concept below.` : 'No results. Try a broader skill name.';
        } catch (error) {
          if (error.name !== 'AbortError') status.textContent = 'Search unavailable. Please try again.';
        }
      }, 300);
    });
  });
}
setupCatalogueSearch();
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
const addRequirement = document.getElementById('add-requirement');
if (addRequirement) {
  addRequirement.addEventListener('click', () => {
    const total = document.querySelector('input[name$="-TOTAL_FORMS"]');
    const count = Number(total.value);
    if (count >= 30) return;
    const template = document.getElementById('empty-requirement');
    const fragment = document.createElement('div');
    // Only trusted, server-rendered form markup is inserted here.
    fragment.innerHTML = template.innerHTML.replaceAll('__prefix__', String(count));
    document.getElementById('requirements').append(...fragment.childNodes);
    setupCatalogueSearch(document.getElementById('requirements'));
    total.value = count + 1;
    if (count + 1 >= 30) addRequirement.disabled = true;
  });
}
