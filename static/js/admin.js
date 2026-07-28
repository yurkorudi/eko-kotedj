const dropdown = document.querySelector(".dropdown");
const button = dropdown.querySelector(".dropdown-btn");

button.addEventListener("click", () => {
    dropdown.classList.toggle("open");
});

document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target)) {
        dropdown.classList.remove("open");
    }
});