document.addEventListener('DOMContentLoaded', () => {
    const homeId = sessionStorage.getItem('home_id');
    if (homeId) {
        document.getElementById('home_id').value = homeId;
    }
});