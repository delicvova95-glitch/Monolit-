export function initCalculator() {
    const section = document.querySelector('[data-calculators]');
    if (!section) return;

    const rates = {
        paver: Number(section.dataset.paverRate) || 50,
        border: Number(section.dataset.borderRate) || 2.5,
    };
    const formatter = new Intl.NumberFormat('ru-RU');

    function numericValue(input) {
        const value = Number(String(input.value).replace(',', '.'));
        return Number.isFinite(value) && value > 0 ? Math.min(value, 1_000_000) : 0;
    }

    section.querySelectorAll('[data-calc]').forEach(card => {
        const product = card.dataset.calc;
        const rate = rates[product] || 0;
        const valueInput = card.querySelector('[data-calc-value]');
        const reserveInput = card.querySelector('[data-calc-reserve]');
        const reserveOutput = card.querySelector('[data-reserve-output]');
        const reserveRow = card.querySelector('[data-row-reserve]');
        const reservePct = card.querySelector('[data-reserve-pct]');
        const reserveQty = card.querySelector('[data-reserve-qty]');
        const baseResult = card.querySelector('[data-base-result]');
        const totalResult = card.querySelector('[data-total-result]');
        const totalLabel = card.querySelector('[data-total-label]');

        function calculate() {
            const reserve = reserveInput ? Math.min(20, Math.max(0, numericValue(reserveInput))) : 0;
            const raw = numericValue(valueInput) * rate;
            const base = Math.ceil(raw);
            const total = Math.ceil(raw * (1 + reserve / 100));

            if (reserveOutput) reserveOutput.value = `${reserve}%`;
            if (reserveRow) reserveRow.hidden = reserve === 0;
            if (reservePct) reservePct.textContent = reserve;
            if (reserveQty) reserveQty.textContent = formatter.format(total - base);
            if (baseResult) baseResult.value = formatter.format(base);
            totalResult.value = formatter.format(total);
            if (totalLabel) totalLabel.textContent = reserve > 0 ? 'С учётом запаса' : 'Необходимое количество';
            return { product, base, total };
        }

        valueInput.addEventListener('input', calculate);
        reserveInput?.addEventListener('input', calculate);

        card.querySelector('[data-use-calculation]')?.addEventListener('click', () => {
            const result = calculate();
            const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            const target = document.querySelector(`#order [name="${result.product}_qty"]`);
            if (target) target.value = result.total;
            document.querySelector('#order')?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' });
            window.setTimeout(() => document.querySelector('#order [name="city"]')?.focus({ preventScroll: true }), reducedMotion ? 0 : 650);
        });

        calculate();
    });
}
