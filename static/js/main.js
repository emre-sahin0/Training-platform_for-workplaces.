// Video player controls
document.addEventListener('DOMContentLoaded', function() {
    const videoPlayer = document.getElementById('videoPlayer');
    if (videoPlayer) {
        // Prevent right-click
        videoPlayer.addEventListener('contextmenu', function(e) {
            e.preventDefault();
        });

        // Prevent keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.target === videoPlayer) {
                if (e.key === ' ' || e.key === 'k' || e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                    e.preventDefault();
                }
            }
        });

        // Prevent seeking
        videoPlayer.addEventListener('seeking', function(e) {
            if (videoPlayer.currentTime < videoPlayer.duration - 1) {
                videoPlayer.currentTime = videoPlayer.duration - 1;
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