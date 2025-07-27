// Video player controls - Sadece geri sarma izinli
document.addEventListener('DOMContentLoaded', function() {
    const videoPlayer = document.getElementById('videoPlayer');
    if (videoPlayer) {
        let maxWatchedTime = 0; // Kullanıcının en fazla izlediği süre
        
        console.log('Video player: Sadece geri sarma izinli!');
        
        // Video oynarken maksimum izlenen süreyi takip et
        videoPlayer.addEventListener('timeupdate', function() {
            if (!videoPlayer.seeking) {
                // Video normal oynarken, maksimum süreyi güncelle
                if (videoPlayer.currentTime > maxWatchedTime) {
                    maxWatchedTime = videoPlayer.currentTime;
                }
            }
        });
        
        // Seeking kontrolü: sadece geri sarmaya izin ver
        videoPlayer.addEventListener('seeking', function() {
            if (videoPlayer.currentTime > maxWatchedTime) {
                // İleri sarma engelle - maksimum izlenen yere geri döndür
                videoPlayer.currentTime = maxWatchedTime;
                console.log('İleri sarma engellendi! Maksimum süre:', maxWatchedTime);
            } else {
                // Geri sarma izinli
                console.log('Geri sarma izinli:', videoPlayer.currentTime);
            }
        });
    }
});

// Form validation
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
});

// Progress bar animation
document.addEventListener('DOMContentLoaded', function() {
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        const width = bar.getAttribute('aria-valuenow');
        bar.style.width = '0%';
        setTimeout(() => {
            bar.style.transition = 'width 1s ease-in-out';
            bar.style.width = width + '%';
        }, 100);
    });
});

// MODERN HOMEPAGE ANIMATIONS
document.addEventListener('DOMContentLoaded', function() {
    
    // Animated Counter Function
    function animateCounter(element, target, duration = 2000) {
        let start = 0;
        const increment = target / (duration / 16);
        
        function updateCounter() {
            start += increment;
            if (start < target) {
                element.textContent = Math.floor(start);
                requestAnimationFrame(updateCounter);
            } else {
                element.textContent = target;
            }
        }
        updateCounter();
    }
    
    // Intersection Observer for animations
    const observerOptions = {
        threshold: 0.3,
        rootMargin: '0px 0px -50px 0px'
    };
    
    // Stats Counter Animation
    const statsObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const statNumbers = entry.target.querySelectorAll('.stat-number');
                statNumbers.forEach(stat => {
                    const target = parseInt(stat.getAttribute('data-count'));
                    if (target && !stat.classList.contains('animated')) {
                        stat.classList.add('animated');
                        animateCounter(stat, target, 2500);
                    }
                });
                statsObserver.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Feature Cards Animation
    const cardsObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                cardsObserver.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Initialize Observers
    const statsSection = document.querySelector('.stats-section');
    if (statsSection) {
        statsObserver.observe(statsSection);
    }
    
    const featureCards = document.querySelectorAll('.feature-card');
    featureCards.forEach((card, index) => {
        // Initial state for animation
        card.style.opacity = '0';
        card.style.transform = 'translateY(50px)';
        card.style.transition = `opacity 0.6s ease ${index * 0.1}s, transform 0.6s ease ${index * 0.1}s`;
        cardsObserver.observe(card);
    });
    
    // Parallax Effect for Floating Elements
    function updateParallax() {
        const scrolled = window.pageYOffset;
        const parallaxElements = document.querySelectorAll('.floating-circle');
        
        parallaxElements.forEach((element, index) => {
            const speed = 0.2 + (index * 0.1);
            const yPos = -(scrolled * speed);
            element.style.transform = `translate3d(0, ${yPos}px, 0)`;
        });
    }
    
    // Throttled scroll event for performance
    let ticking = false;
    function requestTick() {
        if (!ticking) {
            requestAnimationFrame(updateParallax);
            ticking = true;
            setTimeout(() => { ticking = false; }, 16);
        }
    }
    
    window.addEventListener('scroll', requestTick);
    
    // Modern Button Hover Effects
    const modernBtns = document.querySelectorAll('.modern-btn');
    modernBtns.forEach(btn => {
        btn.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px) scale(1.02)';
        });
        
        btn.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
        
        btn.addEventListener('mousedown', function() {
            this.style.transform = 'translateY(0) scale(0.98)';
        });
        
        btn.addEventListener('mouseup', function() {
            this.style.transform = 'translateY(-2px) scale(1.02)';
        });
    });
    
    // Gradient Text Animation
    const gradientTexts = document.querySelectorAll('.gradient-text');
    gradientTexts.forEach(text => {
        text.addEventListener('mouseenter', function() {
            this.style.animationDuration = '1s';
        });
        
        text.addEventListener('mouseleave', function() {
            this.style.animationDuration = '3s';
        });
    });
    
    // Hero Badge Animation
    const heroBadge = document.querySelector('.hero-badge');
    if (heroBadge) {
        setInterval(() => {
            heroBadge.style.transform = 'scale(1.05)';
            setTimeout(() => {
                heroBadge.style.transform = 'scale(1)';
            }, 200);
        }, 3000);
    }
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Add loading animation to page
    window.addEventListener('load', function() {
        document.body.style.opacity = '0';
        document.body.style.transition = 'opacity 0.5s ease-in-out';
        
        setTimeout(() => {
            document.body.style.opacity = '1';
        }, 100);
    });
    
    // Feature card hover sound effect (optional)
    const featureCardsWithHover = document.querySelectorAll('.feature-card');
    featureCardsWithHover.forEach(card => {
        card.addEventListener('mouseenter', function() {
            // Add a subtle scale effect
            this.style.transform = 'translateY(-15px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });
    
    // Mobile touch effects
    if ('ontouchstart' in window) {
        modernBtns.forEach(btn => {
            btn.addEventListener('touchstart', function() {
                this.style.transform = 'scale(0.95)';
            });
            
            btn.addEventListener('touchend', function() {
                setTimeout(() => {
                    this.style.transform = 'scale(1)';
                }, 150);
            });
        });
    }
    
    // Preload animations
    function preloadAnimations() {
        const style = document.createElement('style');
        style.textContent = `
            .feature-card { will-change: transform; }
            .modern-btn { will-change: transform; }
            .floating-circle { will-change: transform; }
            .gradient-text { will-change: filter; }
        `;
        document.head.appendChild(style);
    }
    
    preloadAnimations();
});

// Performance optimization: Reduce animations on low-end devices
if (navigator.hardwareConcurrency <= 2 || navigator.deviceMemory <= 4) {
    document.documentElement.style.setProperty('--animation-duration', '0.1s');
} 