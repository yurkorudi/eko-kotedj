document.addEventListener('DOMContentLoaded', () => {
    const homeId = sessionStorage.getItem('home_id');
    const homeInput = document.getElementById('home_id');
    if (homeId && homeInput && !homeInput.value) {
        homeInput.value = homeId;
    }
});
