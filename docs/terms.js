(() => {
  const terms = Array.from(document.querySelectorAll('[data-term]'));

  const closeTerms = (except) => {
    terms.forEach((term) => {
      if (term !== except) {
        term.querySelector('.term__trigger')?.setAttribute('aria-expanded', 'false');
      }
    });
  };

  terms.forEach((term) => {
    const trigger = term.querySelector('.term__trigger');
    if (!trigger) return;

    trigger.addEventListener('click', () => {
      const willOpen = trigger.getAttribute('aria-expanded') !== 'true';
      closeTerms(term);
      trigger.setAttribute('aria-expanded', String(willOpen));
    });

    trigger.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        trigger.setAttribute('aria-expanded', 'false');
        trigger.blur();
      }
    });
  });

  document.addEventListener('click', (event) => {
    if (!event.target.closest('[data-term]')) closeTerms();
  });
})();
