export function initOrderForm() {
    const forms = [...document.querySelectorAll('[data-order-form]')];
    if (!forms.length) return;

    forms.forEach(form => {
        const status = form.querySelector('[data-form-status]');
        const submit = form.querySelector('[type="submit"]');
        const submitLabel = submit.querySelector('span');

        function clearErrors() {
            form.querySelectorAll('[data-error-for]').forEach(element => { element.textContent = ''; });
            form.querySelectorAll('.has-error').forEach(element => element.classList.remove('has-error'));
        }

        function showErrors(errors) {
            Object.entries(errors).forEach(([field, message]) => {
                const output = form.querySelector(`[data-error-for="${field}"]`);
                if (output) output.textContent = message;
                form.elements[field]?.closest('.field')?.classList.add('has-error');
            });
            const first = form.querySelector('.has-error input, .has-error textarea');
            first?.focus();
        }

        function showStatus(message, success) {
            status.textContent = message;
            status.classList.add('is-visible');
            status.classList.toggle('is-success', success);
            status.classList.toggle('is-error', !success);
        }

        form.addEventListener('input', event => {
            const field = event.target.name;
            const output = form.querySelector(`[data-error-for="${field}"]`);
            if (output) output.textContent = '';
            event.target.closest('.field')?.classList.remove('has-error');
        });

        form.addEventListener('submit', async event => {
            event.preventDefault();
            clearErrors();
            status.classList.remove('is-visible');

            if (!form.checkValidity()) {
                form.reportValidity();
                return;
            }

            const data = Object.fromEntries(new FormData(form).entries());
            data.consent = form.elements.consent.checked;
            submit.disabled = true;
            submitLabel.textContent = 'Отправляем…';

            try {
                const response = await fetch(form.action || '/api/orders', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content,
                        'Accept': 'application/json',
                    },
                    body: JSON.stringify(data),
                });
                const result = await response.json();
                if (!response.ok) {
                    if (result.errors) showErrors(result.errors);
                    throw new Error(result.message || 'Не удалось отправить заявку.');
                }
                form.reset();
                if (form.elements.paver_qty) form.elements.paver_qty.value = 0;
                if (form.elements.border_qty) form.elements.border_qty.value = 0;
                showStatus(result.message, true);
            } catch (error) {
                showStatus(error.message || 'Ошибка соединения. Проверьте интернет и повторите отправку.', false);
            } finally {
                submit.disabled = false;
                submitLabel.textContent = 'Отправить заявку';
            }
        });
    });
}
