import { initCalculator } from './calculator.js?v=20261109-premium-3';
import { initOrderForm } from './form.js?v=20261109-premium-3';
import { initGallery } from './gallery.js';

const header = document.querySelector('[data-header]');
const menuButton = document.querySelector('[data-menu-toggle]');
const navigation = document.querySelector('[data-nav]');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const scrollBehavior = reducedMotion.matches ? 'auto' : 'smooth';
let scrollQueued = false;

function updateHeader() {
    header?.classList.toggle('is-scrolled', window.scrollY > 24);
    scrollQueued = false;
}

window.addEventListener('scroll', () => {
    if (!scrollQueued) {
        scrollQueued = true;
        requestAnimationFrame(updateHeader);
    }
}, { passive: true });
updateHeader();

function closeMenu() {
    menuButton?.setAttribute('aria-expanded', 'false');
    navigation?.classList.remove('is-open');
    document.body.classList.remove('menu-open');
}

menuButton?.addEventListener('click', () => {
    const open = menuButton.getAttribute('aria-expanded') !== 'true';
    menuButton.setAttribute('aria-expanded', String(open));
    navigation?.classList.toggle('is-open', open);
    document.body.classList.toggle('menu-open', open);
});
navigation?.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
window.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeMenu();
});

document.querySelectorAll('[data-current-year]').forEach(element => {
    element.textContent = new Date().getFullYear();
});

document.querySelectorAll('.faq-list details').forEach(item => {
    item.addEventListener('toggle', () => {
        if (!item.open) return;
        document.querySelectorAll('.faq-list details[open]').forEach(other => {
            if (other !== item) other.open = false;
        });
    });
});

document.querySelectorAll('[data-order-product]').forEach(button => {
    button.addEventListener('click', () => {
        const form = document.querySelector('#order [data-order-form]');
        const comment = form?.elements.comment;
        if (comment) {
            const message = `Интересует: ${button.dataset.orderProduct}.`;
            if (!comment.value.includes(message)) {
                comment.value = `${message}${comment.value ? `\n${comment.value}` : ''}`;
            }
        }
        document.querySelector('#order')?.scrollIntoView({ behavior: scrollBehavior });
        window.setTimeout(() => form?.elements.name.focus({ preventScroll: true }), reducedMotion.matches ? 0 : 650);
    });
});

const contactWidget = document.querySelector('[data-contact-widget]');
if (contactWidget) {
    const heroBlock = document.querySelector('[data-hero]');
    if (heroBlock) {
        const toggleVisibility = () => {
            contactWidget.classList.toggle('is-visible', window.scrollY > 40);
        };
        toggleVisibility();
        window.addEventListener('scroll', toggleVisibility, { passive: true });
    } else {
        contactWidget.classList.add('is-visible');
    }

    const toggle = contactWidget.querySelector('[data-contact-widget-toggle]');
    const popup = contactWidget.querySelector('[data-contact-widget-popup]');
    let returnFocus = toggle;

    const setOpen = (open, opener = toggle) => {
        if (open && !popup.open) {
            returnFocus = opener;
            popup.showModal();
            toggle.setAttribute('aria-expanded', 'true');
            contactWidget.classList.add('is-open');
            window.setTimeout(() => popup.querySelector('[name="name"]')?.focus(), 0);
        } else if (!open && popup.open) {
            popup.close();
        }
    };

    toggle.addEventListener('click', () => setOpen(!popup.open));
    contactWidget.querySelector('[data-contact-widget-close]')?.addEventListener('click', () => setOpen(false));
    popup.addEventListener('close', () => {
        toggle.setAttribute('aria-expanded', 'false');
        contactWidget.classList.remove('is-open');
        returnFocus?.focus({ preventScroll: true });
    });
    popup.addEventListener('click', event => {
        if (event.target !== popup) return;
        const rect = popup.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) {
            setOpen(false);
        }
    });
    document.querySelector('[data-mobile-contact]')?.addEventListener('click', event => {
        setOpen(true, event.currentTarget);
    });
    document.querySelector('[data-delivery-order]')?.addEventListener('click', event => {
        const comment = popup.querySelector('[name="comment"]');
        const message = 'Хочу уточнить стоимость и условия доставки.';
        if (comment && !comment.value.includes(message)) {
            comment.value = `${message}${comment.value ? `\n${comment.value}` : ''}`;
        }
        setOpen(true, event.currentTarget);
    });
}

initCalculator();
initOrderForm();
initGallery();

if (!reducedMotion.matches && 'IntersectionObserver' in window) {
    const revealTargets = document.querySelectorAll(
        '.section-heading, .product-card, .feature-card, .calc-card, .gallery-item, .delivery-content, .delivery-media, .faq-list details, .contact-item, .order-intro, .order-form',
    );
    revealTargets.forEach(element => element.classList.add('reveal-init'));
    const revealObserver = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-in');
                revealObserver.unobserve(entry.target);
            }
        });
    }, { rootMargin: '0px 0px -8% 0px', threshold: .08 });
    revealTargets.forEach(element => revealObserver.observe(element));
}

const canRender3D = window.matchMedia('(min-width: 801px)').matches && !reducedMotion.matches;
if (canRender3D && document.querySelector('#scene')) {
    import('./three-scene.js?v=20261109-premium-3')
        .then(module => module.initThreeScene())
        .catch(() => document.querySelector('[data-scene-loader]')?.remove());
}
