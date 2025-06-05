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