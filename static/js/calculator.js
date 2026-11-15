export function initCalculator() {
    const section = document.querySelector('[data-calculators]');
    if (!section) return;

    const rates = {
        paver: Number(section.dataset.paverRate) || 50,
        border: Number(section.dataset.borderRate) || 1,
    };
    const prices = {
        paver: Number(section.dataset.paverPrice) || 0,
        border: Number(section.dataset.borderPrice) || 0,
    };
    const formatter = new Intl.NumberFormat('ru-RU');
    const results = {};

    function numericValue(input) {
        const value = Number(String(input.value).replace(',', '.'));
        return Number.isFinite(value) && value > 0 ? Math.min(value, 1_000_000) : 0;
    }

    const cards = [...section.querySelectorAll('[data-calc]')].map(card => {
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
        const costResult = card.querySelector('[data-cost-result]');
        const pricePerPiece = rate > 0 ? (prices[product] || 0) / rate : 0;

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
            if (costResult) costResult.value = formatter.format(Math.round(total * pricePerPiece));
            if (totalLabel) totalLabel.textContent = reserve > 0 ? 'С учётом запаса' : 'Необходимое количество';
            results[product] = { product, total, rate };
            return results[product];
        }

        valueInput.addEventListener('input', calculate);
        reserveInput?.addEventListener('input', calculate);
        calculate();
        return calculate;
    });

    // Одна общая кнопка: переносит результаты обоих калькуляторов в форму заявки
    section.querySelectorAll('[data-use-calculation]').forEach(button => {
        button.addEventListener('click', () => {
            cards.forEach(calculate => {
                const result = calculate();
                const target = document.querySelector(`#order [name="${result.product}_qty"]`);
                if (!target) return;
                // Поля формы заказа принимают м² (брусчатка) и пог. м (бордюр), пересчитываем из штук
                target.value = result.rate > 0 ? Math.round((result.total / result.rate) * 100) / 100 : 0;
            });
            const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            document.querySelector('#order')?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' });
            window.setTimeout(() => document.querySelector('#order [name="name"]')?.focus({ preventScroll: true }), reducedMotion ? 0 : 650);
        });
    });
}
