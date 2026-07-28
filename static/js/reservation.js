document.querySelectorAll('.home-reservation-btn').forEach(link => {
    link.addEventListener('click', function () {
        sessionStorage.setItem('home_id', this.dataset.id);
    });
});