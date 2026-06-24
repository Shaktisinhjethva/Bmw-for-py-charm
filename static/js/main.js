document.addEventListener('DOMContentLoaded', () => {
    // Mobile nav toggle
    const toggle = document.querySelector('.mobile-toggle');
    const navLinks = document.querySelector('.nav-links');
    if (toggle && navLinks) {
        toggle.addEventListener('click', () => navLinks.classList.toggle('open'));
    }

    // Animated counters
    document.querySelectorAll('[data-count]').forEach(el => {
        const target = parseFloat(el.dataset.count);
        const suffix = el.dataset.suffix || '';
        const isFloat = target % 1 !== 0;
        const duration = 1500;
        const start = performance.now();

        function update(now) {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = target * eased;
            el.textContent = (isFloat ? current.toFixed(1) : Math.floor(current)) + suffix;
            if (progress < 1) requestAnimationFrame(update);
        }
        requestAnimationFrame(update);
    });

    // 3D tilt effect on cards
    document.querySelectorAll('[data-tilt]').forEach(card => {
        card.addEventListener('mousemove', e => {
            const rect = card.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width - 0.5;
            const y = (e.clientY - rect.top) / rect.height - 0.5;
            card.style.transform = `perspective(800px) rotateY(${x * 12}deg) rotateX(${-y * 12}deg) translateY(-4px)`;
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    });

    // Floating particles in hero
    const particlesEl = document.getElementById('particles');
    if (particlesEl) {
        for (let i = 0; i < 20; i++) {
            const p = document.createElement('div');
            p.style.cssText = `
                position:absolute;
                width:${Math.random() * 4 + 2}px;
                height:${Math.random() * 4 + 2}px;
                background:rgba(16,185,129,${Math.random() * 0.5 + 0.2});
                border-radius:50%;
                left:${Math.random() * 100}%;
                top:${Math.random() * 100}%;
                animation: particleFloat ${Math.random() * 4 + 3}s ease-in-out infinite;
                animation-delay:${Math.random() * 2}s;
            `;
            particlesEl.appendChild(p);
        }
        const style = document.createElement('style');
        style.textContent = `
            @keyframes particleFloat {
                0%, 100% { transform: translateY(0) scale(1); opacity: 0.6; }
                50% { transform: translateY(-30px) scale(1.2); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }

    // Auto-dismiss flash messages
    document.querySelectorAll('.flash').forEach(flash => {
        setTimeout(() => {
            flash.style.transition = 'opacity 0.5s, transform 0.5s';
            flash.style.opacity = '0';
            flash.style.transform = 'translateX(100%)';
            setTimeout(() => flash.remove(), 500);
        }, 4000);
    });
});
