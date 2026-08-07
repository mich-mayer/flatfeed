(() => {
  const carousel = document.querySelector('[data-carousel]');

  if (!carousel) {
    return;
  }

  const stage = carousel.querySelector('.product-carousel__stage');
  const slides = Array.from(carousel.querySelectorAll('[data-carousel-slide]'));
  const previous = carousel.querySelector('[data-carousel-previous]');
  const next = carousel.querySelector('[data-carousel-next]');
  const position = carousel.querySelector('[data-carousel-position]');
  let currentIndex = 0;
  let pointerStart = null;

  const showSlide = (index) => {
    currentIndex = Math.max(0, Math.min(index, slides.length - 1));

    slides.forEach((slide, slideIndex) => {
      const isCurrent = slideIndex === currentIndex;
      slide.hidden = !isCurrent;
      slide.setAttribute('aria-hidden', String(!isCurrent));
    });

    previous.disabled = currentIndex === 0;
    next.disabled = currentIndex === slides.length - 1;
    position.textContent = `Screen ${currentIndex + 1} of ${slides.length}`;
  };

  previous.addEventListener('click', () => showSlide(currentIndex - 1));
  next.addEventListener('click', () => showSlide(currentIndex + 1));

  stage.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      showSlide(currentIndex - 1);
    }

    if (event.key === 'ArrowRight') {
      event.preventDefault();
      showSlide(currentIndex + 1);
    }
  });

  stage.addEventListener('pointerdown', (event) => {
    if (event.pointerType !== 'mouse') {
      pointerStart = event.clientX;
    }
  });

  stage.addEventListener('pointerup', (event) => {
    if (pointerStart === null) {
      return;
    }

    const distance = event.clientX - pointerStart;
    pointerStart = null;

    if (Math.abs(distance) < 50) {
      return;
    }

    showSlide(distance < 0 ? currentIndex + 1 : currentIndex - 1);
  });

  stage.addEventListener('pointercancel', () => {
    pointerStart = null;
  });

  showSlide(0);
})();
