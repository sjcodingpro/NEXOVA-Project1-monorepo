/**
 * Nexova — Talent registration form validation
 * Validates every field defined in CONTEXT.md, shows field-specific error
 * messages, and simulates submission (no backend) on success.
 */
(function () {
  'use strict';

  const form = document.getElementById('talent-form');
  if (!form) return; // validation.js is only wired up on application.html

  const formSection = document.getElementById('form-section');
  const successPanel = document.getElementById('success-panel');
  const successFocus = document.getElementById('success-focus');
  const summaryError = document.getElementById('form-summary-error');
  const clearBtn = document.getElementById('clear-form');

  const fields = {
    fullName: document.getElementById('full-name'),
    email: document.getElementById('email'),
    phone: document.getElementById('phone'),
    country: document.getElementById('country'),
    years: document.getElementById('years-experience'),
    sector: document.getElementById('sector'),
    english: document.getElementById('english-level'),
    linkedin: document.getElementById('linkedin'),
    comments: document.getElementById('comments'),
    consent: document.getElementById('consent'),
  };

  const availabilityRadios = Array.from(
    document.querySelectorAll('input[name="availability"]')
  );
  const availabilityGroup = document.querySelector('[role="radiogroup"]');
  const commentsCount = document.getElementById('comments-count');

  const COMMENTS_MAX = 500;

  function validateFullName(value) {
    const words = value.trim().split(/\s+/).filter(Boolean);
    if (words.length < 2) {
      return 'Name must contain at least first and last name';
    }
    return null;
  }

  function validateEmail(value) {
    const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!value.trim() || !pattern.test(value.trim())) {
      return 'Enter a valid email (example: name@company.com)';
    }
    return null;
  }

  function validatePhone(value) {
    const trimmed = value.trim();
    const compact = trimmed.replace(/[\s-]/g, '');
    const pattern = /^\+\d{7,15}$/;
    if (!pattern.test(compact)) {
      return 'Phone must include country code (example: +34 612 345 678)';
    }
    return null;
  }

  function validateCountry(value) {
    if (!value) {
      return 'Select your country of residence';
    }
    return null;
  }

  function validateYears(value) {
    if (value === '' || value === null) {
      return 'Years of experience must be between 0 and 50';
    }
    const num = Number(value);
    if (Number.isNaN(num) || num < 0 || num > 50) {
      return 'Years of experience must be between 0 and 50';
    }
    return null;
  }

  function validateSector(value) {
    if (!value) {
      return 'Select your sector of interest';
    }
    return null;
  }

  function validateEnglish(value) {
    if (!value) {
      return 'Indicate your English level';
    }
    return null;
  }

  function validateAvailability() {
    const checked = availabilityRadios.some((radio) => radio.checked);
    if (!checked) {
      return 'Select your availability';
    }
    return null;
  }

  function validateLinkedin(value) {
    const trimmed = value.trim();
    if (!trimmed) return null;
    try {
      const url = new URL(trimmed);
      if (url.protocol !== 'http:' && url.protocol !== 'https:') {
        return 'If you include LinkedIn, it must be a valid URL';
      }
    } catch (err) {
      return 'If you include LinkedIn, it must be a valid URL';
    }
    return null;
  }

  function validateComments(value) {
    if (value.length > COMMENTS_MAX) {
      const remaining = COMMENTS_MAX - value.length;
      return `Comments cannot exceed 500 characters (${remaining} remaining)`;
    }
    return null;
  }

  function validateConsent(checked) {
    if (!checked) {
      return 'You must accept the data processing policy to continue';
    }
    return null;
  }

  function showFieldError(fieldId, message, inputEl) {
    const errorEl = document.getElementById(`${fieldId}-error`);
    if (!errorEl) return;

    if (message) {
      errorEl.textContent = message;
      errorEl.hidden = false;
      errorEl.classList.remove('hidden');
      if (inputEl) {
        inputEl.setAttribute('aria-invalid', 'true');
        inputEl.classList.add('border-error', 'focus:ring-error', 'focus:border-error');
        inputEl.classList.remove('focus:ring-teal', 'focus:border-teal');
      }
    } else {
      errorEl.textContent = '';
      errorEl.hidden = true;
      errorEl.classList.add('hidden');
      if (inputEl) {
        inputEl.removeAttribute('aria-invalid');
        inputEl.classList.remove('border-error', 'focus:ring-error', 'focus:border-error');
        inputEl.classList.add('focus:ring-teal', 'focus:border-teal');
      }
    }
  }

  function setGroupError(message) {
    showFieldError('availability', message, null);
    if (availabilityGroup) {
      availabilityGroup.classList.toggle('ring-2', Boolean(message));
      availabilityGroup.classList.toggle('ring-error', Boolean(message));
      availabilityGroup.classList.toggle('rounded-lg', Boolean(message));
    }
  }

  function runFullName() {
    const msg = validateFullName(fields.fullName.value);
    showFieldError('full-name', msg, fields.fullName);
    return msg;
  }

  function runEmail() {
    const msg = validateEmail(fields.email.value);
    showFieldError('email', msg, fields.email);
    return msg;
  }

  function runPhone() {
    const msg = validatePhone(fields.phone.value);
    showFieldError('phone', msg, fields.phone);
    return msg;
  }

  function runCountry() {
    const msg = validateCountry(fields.country.value);
    showFieldError('country', msg, fields.country);
    return msg;
  }

  function runYears() {
    const msg = validateYears(fields.years.value);
    showFieldError('years-experience', msg, fields.years);
    return msg;
  }

  function runSector() {
    const msg = validateSector(fields.sector.value);
    showFieldError('sector', msg, fields.sector);
    return msg;
  }

  function runEnglish() {
    const msg = validateEnglish(fields.english.value);
    showFieldError('english-level', msg, fields.english);
    return msg;
  }

  function runAvailability() {
    const msg = validateAvailability();
    setGroupError(msg);
    return msg;
  }

  function runLinkedin() {
    const msg = validateLinkedin(fields.linkedin.value);
    showFieldError('linkedin', msg, fields.linkedin);
    return msg;
  }

  function runComments() {
    const msg = validateComments(fields.comments.value);
    showFieldError('comments', msg, fields.comments);
    return msg;
  }

  function runConsent() {
    const msg = validateConsent(fields.consent.checked);
    showFieldError('consent', msg, fields.consent);
    return msg;
  }

  function updateCommentsCounter() {
    const remaining = COMMENTS_MAX - fields.comments.value.length;
    commentsCount.textContent = `${remaining} characters remaining`;
  }

  fields.fullName.addEventListener('blur', runFullName);
  fields.fullName.addEventListener('input', () => {
    if (fields.fullName.getAttribute('aria-invalid') === 'true') runFullName();
  });

  fields.email.addEventListener('blur', runEmail);
  fields.email.addEventListener('input', () => {
    if (fields.email.getAttribute('aria-invalid') === 'true') runEmail();
  });

  fields.phone.addEventListener('blur', runPhone);
  fields.phone.addEventListener('input', () => {
    if (fields.phone.getAttribute('aria-invalid') === 'true') runPhone();
  });

  fields.country.addEventListener('change', runCountry);
  fields.country.addEventListener('blur', runCountry);

  fields.years.addEventListener('blur', runYears);
  fields.years.addEventListener('input', () => {
    if (fields.years.getAttribute('aria-invalid') === 'true') runYears();
  });

  fields.sector.addEventListener('change', runSector);
  fields.sector.addEventListener('blur', runSector);

  fields.english.addEventListener('change', runEnglish);
  fields.english.addEventListener('blur', runEnglish);

  availabilityRadios.forEach((radio) => {
    radio.addEventListener('change', runAvailability);
  });

  fields.linkedin.addEventListener('blur', runLinkedin);
  fields.linkedin.addEventListener('input', () => {
    if (fields.linkedin.getAttribute('aria-invalid') === 'true') runLinkedin();
  });

  fields.comments.addEventListener('input', () => {
    updateCommentsCounter();
    runComments();
  });

  fields.consent.addEventListener('change', runConsent);

  clearBtn.addEventListener('click', () => {
    form.reset();

    Object.entries(fields).forEach(([key, el]) => {
      if (!el) return;
      const id = el.id;
      showFieldError(id, null, el);
    });
    setGroupError(null);
    summaryError.classList.add('hidden');
    summaryError.hidden = true;
    updateCommentsCounter();
    fields.fullName.focus();
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    const results = [
      { msg: runFullName(), el: fields.fullName },
      { msg: runEmail(), el: fields.email },
      { msg: runPhone(), el: fields.phone },
      { msg: runCountry(), el: fields.country },
      { msg: runYears(), el: fields.years },
      { msg: runSector(), el: fields.sector },
      { msg: runEnglish(), el: fields.english },
      { msg: runAvailability(), el: availabilityRadios[0] },
      { msg: runLinkedin(), el: fields.linkedin },
      { msg: runComments(), el: fields.comments },
      { msg: runConsent(), el: fields.consent },
    ];

    const firstInvalid = results.find((r) => r.msg);

    if (firstInvalid) {
      summaryError.textContent = 'Please review the highlighted fields before submitting.';
      summaryError.classList.remove('hidden');
      summaryError.hidden = false;
      if (firstInvalid.el && typeof firstInvalid.el.focus === 'function') {
        firstInvalid.el.focus();
      }
      return;
    }

    summaryError.classList.add('hidden');
    summaryError.hidden = true;

    formSection.classList.add('hidden');
    successPanel.classList.remove('hidden');
    successFocus.focus();
    successPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  updateCommentsCounter();
})();