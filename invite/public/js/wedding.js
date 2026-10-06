(() => {
  'use strict';
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const envelope = document.getElementById('envelope');
  const content = document.getElementById('invitation-content');
  const openButton = document.getElementById('open-invitation');
  const hero = document.getElementById('home');
  let revealObserver;
  let petalObserver;
  let openingTimer;
  let scrollFrame;
  let opening = false;
  const storyTimeline = document.querySelector('.timeline');
  let storyGeometry;

  function prepareReveals() {
    if (motionPreference.matches || !('IntersectionObserver' in window)) return;
    // Observe only after the envelope exits, so hero entrances remain visible.
    revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -24px 0px' });
    const selectors = '.hero-copy > *, .hero-visual, .section-heading > *, .countdown > div, .milestone-card, .event-card, .gallery-item, .couple-photo, .travel-note, .rsvp-form, footer > *';
    document.querySelectorAll(selectors).forEach(element => {
      element.classList.add('reveal');
      const siblings = [...element.parentElement.children];
      const delay = Math.min(siblings.indexOf(element) * 85, 450);
      element.style.setProperty('--reveal-delay', `${delay}ms`);
      // A large form must be revealed even when it exceeds the screen height.
      if (element.classList.contains('rsvp-form')) element.style.setProperty('--reveal-delay', '0ms');
      revealObserver.observe(element);
    });
  }

  function addPetals(parent, count) {
    const field = document.createElement('div');
    field.className = 'petal-field';
    field.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < count; i++) {
      const petal = document.createElement('span');
      petal.className = 'floating-petal';
      petal.style.cssText = `--petal-left:${Math.random() * 100}%;--petal-drift:${(Math.random() - .5) * 160}px;--petal-turn:${180 + Math.random() * 360}deg;--petal-duration:${12 + Math.random() * 10}s;--petal-delay:${-Math.random() * 22}s;--petal-size:${7 + Math.random() * 8}px`;
      field.appendChild(petal);
    }
    parent.prepend(field);
    return field;
  }

  if (!motionPreference.matches) {
    addPetals(envelope, 8);
    const heroPetals = addPetals(hero, 12);
    if ('IntersectionObserver' in window) {
      petalObserver = new IntersectionObserver(([entry]) => {
        heroPetals.classList.toggle('is-paused', !entry.isIntersecting);
      });
      petalObserver.observe(hero);
    }
    document.querySelectorAll('.botanical path').forEach(path => {
      path.style.setProperty('--stroke-length', path.getTotalLength());
    });
  }

  function enterInvitation() {
    clearTimeout(openingTimer);
    envelope.hidden = true;
    content.inert = false;
    content.classList.add('invitation-open');
    document.body.style.overflow = '';
    prepareReveals();
    document.querySelector('.monogram').focus({ preventScroll: true });
    updateScrollMotion();
  }

  if (!window.location.hash) {
    envelope.hidden = false;
    content.inert = true;
    document.body.style.overflow = 'hidden';
    openButton.focus();
  } else {
    content.classList.add('invitation-open');
    prepareReveals();
  }
  openButton.addEventListener('click', () => {
    if (opening) return;
    opening = true;
    openButton.disabled = true;
    envelope.classList.add('opening');
    openingTimer = window.setTimeout(enterInvitation, motionPreference.matches ? 0 : 2200);
  });

  function measureStoryPath() {
    if (!storyTimeline) return;
    const mapping = storyTimeline.querySelector('.timeline-mapping');
    const markers = [...storyTimeline.querySelectorAll('.timeline-dot')];
    // Offset coordinates ignore reveal transforms, keeping the path anchored.
    const points = markers.map(marker => {
      let x = marker.offsetWidth / 2;
      let y = marker.offsetHeight / 2;
      for (let element = marker; element && element !== storyTimeline; element = element.offsetParent) {
        x += element.offsetLeft;
        y += element.offsetTop;
      }
      return { x, y, marker };
    });
    mapping.setAttribute('viewBox', `0 0 ${storyTimeline.offsetWidth} ${storyTimeline.offsetHeight}`);
    mapping.querySelector('mask').setAttribute('width', storyTimeline.offsetWidth);
    mapping.querySelector('mask').setAttribute('height', storyTimeline.offsetHeight);
    let path = '';
    points.forEach((point, index) => {
      if (!index) { path = `M ${point.x} ${point.y}`; return; }
      const previous = points[index - 1];
      const bend = (point.y - previous.y) * .45;
      path += ` C ${previous.x} ${previous.y + bend}, ${point.x} ${point.y - bend}, ${point.x} ${point.y}`;
    });
    mapping.querySelectorAll('path').forEach(element => element.setAttribute('d', path));
    const trace = mapping.querySelector('.timeline-mask');
    const length = trace.getTotalLength();
    trace.setAttribute('stroke-dasharray', `${length} ${length}`);
    storyGeometry = { points, trace, length };
    storyTimeline.classList.add('has-mapping');
    updateStoryTrace();
  }

  function updateStoryTrace() {
    if (!storyGeometry || !storyGeometry.points.length) return;
    const { points, trace, length } = storyGeometry;
    const target = window.innerHeight * .65 - storyTimeline.getBoundingClientRect().top;
    let travelled = 0;
    if (motionPreference.matches || target >= points[points.length - 1].y) {
      travelled = length;
    } else if (target > points[0].y && length) {
      // Match the drawn length to the viewport's reading line along the curve.
      let low = 0;
      let high = length;
      for (let i = 0; i < 12; i++) {
        const middle = (low + high) / 2;
        if (trace.getPointAtLength(middle).y < target) low = middle;
        else high = middle;
      }
      travelled = (low + high) / 2;
    }
    trace.setAttribute('stroke-dashoffset', length - travelled);
    points.forEach(point => {
      point.marker.classList.toggle('is-reached', motionPreference.matches || target >= point.y);
    });
  }

  function updateScrollMotion() {
    scrollFrame = undefined;
    const maximum = document.documentElement.scrollHeight - window.innerHeight;
    const progress = maximum > 0 ? Math.min(1, Math.max(0, window.scrollY / maximum)) : 0;
    document.querySelector('.reading-progress').style.transform = `scaleX(${progress})`;
    updateStoryTrace();
    if (motionPreference.matches) return;
    const bounds = hero.getBoundingClientRect();
    if (bounds.bottom > 0 && bounds.top < window.innerHeight) {
      hero.style.setProperty('--parallax-y', `${Math.min(60, Math.max(0, -bounds.top * .08))}px`);
    }
  }
  function queueScrollMotion() {
    if (scrollFrame === undefined) scrollFrame = requestAnimationFrame(updateScrollMotion);
  }
  window.addEventListener('scroll', queueScrollMotion, { passive: true });
  window.addEventListener('resize', () => { measureStoryPath(); queueScrollMotion(); }, { passive: true });
  measureStoryPath();
  if (storyTimeline && 'ResizeObserver' in window) {
    const storyResizeObserver = new ResizeObserver(() => { measureStoryPath(); queueScrollMotion(); });
    storyResizeObserver.observe(storyTimeline);
  }
  storyTimeline?.querySelectorAll('img').forEach(image => image.addEventListener('load', measureStoryPath));
  document.fonts?.ready.then(measureStoryPath);
  updateScrollMotion();
  document.addEventListener('visibilitychange', () => {
    document.body.classList.toggle('motion-paused', document.hidden);
  });
  motionPreference.addEventListener('change', () => {
    if (!motionPreference.matches) return;
    revealObserver?.disconnect();
    petalObserver?.disconnect();
    document.querySelectorAll('.reveal').forEach(element => element.classList.add('is-visible'));
    document.querySelectorAll('.petal-field, .celebration-confetti, .celebration-heart').forEach(element => element.remove());
    hero.style.setProperty('--parallax-y', '0px');
    updateStoryTrace();
    if (opening && !envelope.hidden) enterInvitation();
  });

  function celebrate() {
    if (motionPreference.matches) return;
    const palette = getComputedStyle(document.documentElement);
    const colors = [1, 2, 3, 4, 5].map(index => palette.getPropertyValue(`--confetti-${index}`).trim());
    for (let i = 0; i < 56; i++) {
      const confetti = document.createElement('span');
      confetti.className = 'celebration-confetti';
      confetti.setAttribute('aria-hidden', 'true');
      confetti.style.cssText = `--confetti-left:${Math.random() * 100}%;--confetti-drift:${(Math.random() - .5) * 280}px;--confetti-turn:${Math.random() * 900 - 450}deg;--confetti-color:${colors[i % colors.length]};--confetti-delay:${Math.random() * .7}s;--confetti-duration:${2.8 + Math.random() * 1.5}s`;
      document.body.appendChild(confetti);
      setTimeout(() => confetti.remove(), 5200);
    }
  }
  const weddingDate = new Date(document.body.dataset.weddingDate).getTime();
  let timer;
  function countdown() {
    const remaining = Math.max(0, Math.floor((weddingDate - Date.now()) / 1000));
    const values = { days: Math.floor(remaining / 86400), hours: Math.floor(remaining / 3600) % 24, minutes: Math.floor(remaining / 60) % 60, seconds: remaining % 60 };
    Object.entries(values).forEach(([unit, value]) => {
      const number = document.querySelector(`[data-unit="${unit}"]`);
      const next = String(value).padStart(2, '0');
      if (number.textContent === next) return;
      const initial = number.textContent === '—';
      number.textContent = next;
      if (!initial && !motionPreference.matches && typeof number.animate === 'function') {
        number.animate([{ opacity: .35, transform: 'translateY(-6px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 300, easing: 'ease-out' });
      }
    });
    if (remaining === 0) {
      document.getElementById('countdown-label').textContent = 'Our forever has begun';
      clearInterval(timer);
    }
  }
  timer = setInterval(countdown, 1000);
  countdown();
  const dialog = document.getElementById('photo-dialog');
  document.querySelectorAll('[data-photo]').forEach(button => {
    button.addEventListener('click', () => {
      dialog.querySelector('img').src = button.dataset.photo;
      dialog.querySelector('img').alt = button.dataset.caption;
      dialog.querySelector('p').textContent = button.dataset.caption;
      dialog.showModal();
    });
  });
  dialog.querySelector('button').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  const music = document.getElementById('wedding-music');
  const musicToggle = document.getElementById('music-toggle');
  if (music) musicToggle.addEventListener('click', async () => {
    if (music.paused) {
      try {
        await music.play();
        musicToggle.setAttribute('aria-pressed', 'true');
        musicToggle.setAttribute('aria-label', 'Pause background music');
        musicToggle.querySelector('span').textContent = 'Pause music';
      } catch {
        musicToggle.querySelector('span').textContent = 'Music unavailable';
      }
    } else {
      music.pause();
      musicToggle.setAttribute('aria-pressed', 'false');
      musicToggle.setAttribute('aria-label', 'Play background music');
      musicToggle.querySelector('span').textContent = 'Play music';
    }
  });
  const form = document.getElementById('rsvp-form');
  if (!form) return;
  form.elements.attendance.addEventListener('change', () => {
    const declining = form.elements.attendance.value === 'Not Attending';
    document.getElementById('attending-fields').hidden = declining;
    form.elements.guest_count.disabled = declining;
    form.elements.dietary_requirements.disabled = declining;
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const submit = form.querySelector('button[type="submit"]');
    const status = document.getElementById('rsvp-status');
    submit.disabled = true;
    status.textContent = 'Sending your response…';
    const payload = Object.fromEntries(new FormData(form));
    payload.route = document.body.dataset.route;
    payload.guest_count = payload.guest_count || 0;
    try {
      const response = await fetch('/api/method/invite.api.submit_rsvp', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok || !result.message?.success) {
        let message = 'Unable to send your RSVP. Please try again.';
        try {
          const messages = JSON.parse(result._server_messages || '[]');
          if (messages.length) {
            const server = JSON.parse(messages[0]).message;
            const text = new DOMParser().parseFromString(server, 'text/html').body.textContent;
            if (text) message = text;
          }
        } catch { /* Use the default message if the server response is malformed. */ }
        throw new Error(message);
      }
      status.textContent = payload.attendance === 'Attending' ? 'Thank you! We can’t wait to celebrate with you. ♡' : 'Thank you for letting us know. You’ll be with us in spirit. ♡';
      submit.textContent = 'RSVP sent ♡';
      form.querySelectorAll('input, select, textarea').forEach(input => { input.disabled = true; });
      form.classList.add('rsvp-complete');
      celebrate();
    } catch (error) {
      status.textContent = error.message || 'Connection failed. Please try again.';
      submit.disabled = false;
    }
  });
})();
