// ==================== IMAGE OPTIMIZATION ====================

// Preload hero images for faster initial display
function preloadHeroImages() {
    const heroImages = [
        '/static/images/13.png',
        '/static/images/11.png',
        '/static/images/12.png'
    ];
    
    heroImages.forEach(src => {
        const img = new Image();
        img.src = src;
    });
}

// Optimize lazy-loaded images with intersection observer
function optimizeLazyImages() {
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                
                // Ensure image has loaded
                if (img.tagName === 'IMG' && !img.dataset.optimized) {
                    // Pre-fetch next image in carousel if applicable
                    if (img.classList.contains('hero-slide')) {
                        const nextSlide = img.nextElementSibling || img.parentElement.firstElementChild;
                        if (nextSlide && nextSlide.classList.contains('hero-slide')) {
                            const nextImg = new Image();
                            nextImg.src = nextSlide.src;
                        }
                    }
                    
                    img.dataset.optimized = 'true';
                    observer.unobserve(img);
                }
            }
        });
    }, {
        rootMargin: '50px'
    });
    
    // Observe all lazy-loaded images
    document.querySelectorAll('img[loading="lazy"]').forEach(img => {
        imageObserver.observe(img);
    });
}

// Call image optimization on DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        preloadHeroImages();
        setTimeout(optimizeLazyImages, 100);
    });
} else {
    preloadHeroImages();
    optimizeLazyImages();
}

// ==================== SCROLL ANIMATIONS ====================

// Fade-in sections on scroll
function observeSections() {
    const sections = document.querySelectorAll('.fade-in-section');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });
    
    sections.forEach(section => observer.observe(section));
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', observeSections);
} else {
    observeSections();
}

// ==================== SMOOTH SCROLL ====================

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        const href = this.getAttribute('href');
        if (href !== '#') {
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        }
    });
});

// ==================== BUTTON HOVER EFFECTS ====================

document.querySelectorAll('.btn-primary, .btn-secondary').forEach(btn => {
    btn.addEventListener('mouseenter', function() {
        this.style.transform = 'scale(1.05)';
    });
    
    btn.addEventListener('mouseleave', function() {
        this.style.transform = 'scale(1)';
    });
});

// ==================== SCROLL TO TOP ====================

function createScrollTopButton() {
    const button = document.createElement('button');
    button.id = 'scroll-top-btn';
    button.innerHTML = '↑';
    button.style.cssText = `
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background-color: #ff6b35;
        color: white;
        border: none;
        cursor: pointer;
        display: none;
        font-size: 24px;
        z-index: 100;
        box-shadow: 0 4px 15px rgba(255, 107, 53, 0.3);
        transition: all 0.3s ease;
    `;
    
    document.body.appendChild(button);
    
    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            button.style.display = 'block';
        } else {
            button.style.display = 'none';
        }
    });
    
    button.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
    
    button.addEventListener('mouseenter', function() {
        this.style.transform = 'scale(1.1)';
    });
    
    button.addEventListener('mouseleave', function() {
        this.style.transform = 'scale(1)';
    });
}

createScrollTopButton();

// ==================== NAVBAR STICKY EFFECT ====================

const navbar = document.querySelector('nav');
let lastScrollY = 0;

window.addEventListener('scroll', () => {
    if (window.scrollY > 100) {
        navbar.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.1)';
    } else {
        navbar.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.1)';
    }
});

// ==================== FORM VALIDATION ====================

const form = document.querySelector('form');
if (form) {
    form.addEventListener('submit', function(e) {
        const name = document.getElementById('name');
        const email = document.getElementById('email');
        const subject = document.getElementById('subject');
        const message = document.getElementById('message');
        
        if (!name.value.trim()) {
            alert('Please enter your name');
            e.preventDefault();
            name.focus();
            return false;
        }
        
        if (!email.value.trim() || !email.value.includes('@')) {
            alert('Please enter a valid email address');
            e.preventDefault();
            email.focus();
            return false;
        }
        
        if (!subject.value) {
            alert('Please select a subject');
            e.preventDefault();
            subject.focus();
            return false;
        }
        
        if (!message.value.trim() || message.value.length < 10) {
            alert('Please enter a message (at least 10 characters)');
            e.preventDefault();
            message.focus();
            return false;
        }
        
        return true;
    });
}

// ==================== ANIMATED COUNTERS ====================

function animateValue(element, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        element.textContent = Math.floor(progress * (end - start) + start);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            element.textContent = end;
        }
    };
    window.requestAnimationFrame(step);
}

// ==================== UTILITIES ====================

// Add animation delay utility
const rootStyle = document.documentElement ? document.documentElement.style : null;
if (rootStyle) {
    rootStyle.setProperty('--animation-delay-1', '0.1s');
    rootStyle.setProperty('--animation-delay-2', '0.2s');
    rootStyle.setProperty('--animation-delay-3', '0.3s');
    rootStyle.setProperty('--animation-delay-4', '0.4s');
}

// ==================== HERO TYPEWRITER ====================

function initTypewriter() {
    const target = document.getElementById('typewriter');
    const cursor = document.querySelector('.cursor');

    if (!target || !cursor) return;

    const words = ['thriving learner', 'creative thinker', 'future leader'];
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion) {
        target.textContent = words[0];
        cursor.style.display = 'none';
        return;
    }

    let wordIndex = 0;
    let charIndex = 0;
    let isDeleting = false;
    let timerId = null;

    const tick = () => {
        const word = words[wordIndex];
        const visibleText = isDeleting ? word.slice(0, charIndex - 1) : word.slice(0, charIndex + 1);

        target.textContent = visibleText;
        charIndex = visibleText.length;

        let delay = isDeleting ? 60 : 110;

        if (!isDeleting && charIndex === word.length) {
            delay = 1400;
            isDeleting = true;
        } else if (isDeleting && charIndex === 0) {
            isDeleting = false;
            wordIndex = (wordIndex + 1) % words.length;
            delay = 300;
        }

        timerId = window.setTimeout(tick, delay);
    };

    tick();

    window.addEventListener('beforeunload', () => {
        if (timerId) window.clearTimeout(timerId);
    }, { once: true });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTypewriter);
} else {
    initTypewriter();
}

console.log('Revled animations loaded successfully! 🚀');
