export function initGallery() {
    const gallery = document.querySelector('[data-gallery]');
    const dialog = document.querySelector('[data-lightbox]');
    if (!gallery || !dialog) return;

    const items = [...gallery.querySelectorAll('[data-gallery-index]')];
    const image = dialog.querySelector('[data-lightbox-image]');
    const caption = dialog.querySelector('[data-lightbox-caption]');
    let current = 0;

    function show(index) {
        current = (index + items.length) % items.length;
        const item = items[current];
        image.src = item.dataset.full;
        image.alt = item.dataset.caption || `Фотография ${current + 1}`;
        caption.textContent = item.dataset.caption || '';
        dialog.querySelectorAll('.lightbox-arrow').forEach(button => {
            button.hidden = items.length < 2;
        });
    }

    items.forEach((item, index) => item.addEventListener('click', () => {
        show(index);
        dialog.showModal();
    }));
    dialog.querySelector('[data-lightbox-close]').addEventListener('click', () => dialog.close());
    dialog.querySelector('[data-lightbox-prev]').addEventListener('click', () => show(current - 1));
    dialog.querySelector('[data-lightbox-next]').addEventListener('click', () => show(current + 1));
    dialog.addEventListener('click', event => {
        if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener('keydown', event => {
        if (event.key === 'ArrowLeft') show(current - 1);
        if (event.key === 'ArrowRight') show(current + 1);
    });
}
