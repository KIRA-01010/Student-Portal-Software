/**
 * Student Portal — progressive enhancement.
 *
 *  1. Bootstrap 5 client-side validation for `.needs-validation` forms.
 *  2. Loading state on submit buttons (prevents accidental double posts).
 *  3. Show/hide password toggles.
 *  4. Clears server-rendered `is-invalid` state as soon as the user edits.
 *
 * The server re-validates everything, so nothing here is a security control.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    initFormValidation();
    initPasswordToggles();
    initServerErrorReset();
    autoDismissAlerts();
  });

  /** Bootstrap validation + submit button loading state. */
  function initFormValidation() {
    document.querySelectorAll('form.needs-validation').forEach(function (form) {
      form.addEventListener(
        'submit',
        function (event) {
          if (!form.checkValidity()) {
            event.preventDefault();
            event.stopPropagation();
            form.classList.add('was-validated');
            const firstInvalid = form.querySelector(':invalid');
            if (firstInvalid) firstInvalid.focus();
            return;
          }
          form.classList.add('was-validated');
          setLoading(form);
        },
        false
      );
    });

    // Forms without client validation (e.g. logout) still get the spinner.
    document.querySelectorAll('form:not(.needs-validation)').forEach(function (form) {
      form.addEventListener('submit', function () {
        setLoading(form);
      });
    });
  }

  /** Disable the submit button and swap its label for a spinner. */
  function setLoading(form) {
    const button = form.querySelector('button[type="submit"]');
    if (!button || button.dataset.loading === 'true') return;

    button.dataset.loading = 'true';
    button.disabled = true;

    const spinner = button.querySelector('.spinner-border');
    const label = button.querySelector('.btn-label');
    if (spinner) spinner.classList.remove('d-none');
    if (label && button.dataset.loadingText) label.textContent = button.dataset.loadingText;

    // Safety net: if the navigation is cancelled (validation bounce, back
    // button, offline), restore the button so the form stays usable.
    window.setTimeout(function () {
      resetLoading(button);
    }, 10000);
  }

  function resetLoading(button) {
    if (button.dataset.loading !== 'true') return;
    button.dataset.loading = 'false';
    button.disabled = false;
    const spinner = button.querySelector('.spinner-border');
    if (spinner) spinner.classList.add('d-none');
  }

  /** Restore buttons when the page is served from the bfcache. */
  window.addEventListener('pageshow', function (event) {
    if (!event.persisted) return;
    document.querySelectorAll('button[data-loading="true"]').forEach(resetLoading);
  });

  /** Show/hide password buttons rendered by the `field` macro. */
  function initPasswordToggles() {
    document.querySelectorAll('[data-toggle-password]').forEach(function (button) {
      button.addEventListener('click', function () {
        const input = document.querySelector(button.dataset.togglePassword);
        if (!input) return;

        const revealed = input.type === 'text';
        input.type = revealed ? 'password' : 'text';
        button.setAttribute('aria-label', revealed ? 'Show password' : 'Hide password');

        const icon = button.querySelector('i');
        if (icon) icon.className = revealed ? 'bi bi-eye' : 'bi bi-eye-slash';
      });
    });
  }

  /**
   * Server-side errors arrive as `is-invalid` on the control. Once the user
   * starts fixing the field, drop that class so client validation can take over
   * and the message stops contradicting what they just typed.
   */
  function initServerErrorReset() {
    document.querySelectorAll('.form-control.is-invalid').forEach(function (input) {
      input.addEventListener(
        'input',
        function () {
          input.classList.remove('is-invalid');
          input.removeAttribute('aria-invalid');
        },
        { once: true }
      );
    });
  }

  /** Fade success/info alerts out after a few seconds; keep errors on screen. */
  function autoDismissAlerts() {
    document
      .querySelectorAll('.alert-success.alert-dismissible, .alert-info.alert-dismissible')
      .forEach(function (alert) {
        window.setTimeout(function () {
          if (window.bootstrap && window.bootstrap.Alert) {
            window.bootstrap.Alert.getOrCreateInstance(alert).close();
          }
        }, 6000);
      });
  }
})();
