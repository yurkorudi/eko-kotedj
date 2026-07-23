document.addEventListener("DOMContentLoaded", () => {
    setupHeader();
    setupMenu();
    setupInlineCalendars();
    setupCabinGallery();
    setupLightbox();
    setupFormValidation();
    setupRevealAnimations();
});

function setupHeader() {
    const header = document.querySelector(".site-header");
    if (!header) {
        return;
    }

    const updateHeader = () => {
        header.classList.toggle("is-scrolled", window.scrollY > 24);
    };

    updateHeader();
    window.addEventListener("scroll", updateHeader, { passive: true });
}

function setupMenu() {
    const menuButton = document.querySelector(".menu-toggle");
    const nav = document.querySelector(".main-nav");

    if (!menuButton || !nav) {
        return;
    }

    menuButton.addEventListener("click", () => {
        const isOpen = nav.classList.toggle("is-open");
        menuButton.setAttribute("aria-expanded", String(isOpen));
    });

    nav.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            nav.classList.remove("is-open");
            menuButton.setAttribute("aria-expanded", "false");
        });
    });
}

function setupInlineCalendars() {
    const calendars = document.querySelectorAll("[data-inline-calendar]");
    const blockedDates = getBlockedDates();

    if (!calendars.length || typeof flatpickr === "undefined") {
        return;
    }

    calendars.forEach((calendar) => {
        const form = calendar.closest("form");
        const checkInInput = form.querySelector("[name='check_in']");
        const checkOutInput = form.querySelector("[name='check_out']");
        const checkInLabel = form.querySelector("[data-check-in-label]");
        const checkOutLabel = form.querySelector("[data-check-out-label]");
        const submitButton = form.querySelector("button[type='submit']");
        const defaultDates = [checkInInput.value, checkOutInput.value].filter(Boolean);

        flatpickr(calendar, {
            inline: true,
            mode: "range",
            dateFormat: "Y-m-d",
            minDate: "today",
            locale: "uk",
            disable: blockedDates,
            defaultDate: defaultDates,
            onChange: (selectedDates, dateString, instance) => {
                updateSelectedRange(selectedDates, instance, checkInInput, checkOutInput, checkInLabel, checkOutLabel, submitButton);
            },
            onReady: (selectedDates, dateString, instance) => {
                updateSelectedRange(selectedDates, instance, checkInInput, checkOutInput, checkInLabel, checkOutLabel, submitButton);
            },
        });
    });
}

function updateSelectedRange(selectedDates, instance, checkInInput, checkOutInput, checkInLabel, checkOutLabel, submitButton) {
    const [startDate, endDate] = selectedDates;
    const startValue = startDate ? instance.formatDate(startDate, "Y-m-d") : "";
    const endValue = endDate ? instance.formatDate(endDate, "Y-m-d") : "";

    checkInInput.value = startValue;
    checkOutInput.value = endValue;
    checkInLabel.textContent = startValue || "Оберіть дату";
    checkOutLabel.textContent = endValue || "Оберіть дату";

    if (submitButton) {
        submitButton.disabled = !(startValue && endValue);
    }
}

function getBlockedDates() {
    const dataElement = document.getElementById("blocked-dates-data");
    if (!dataElement) {
        return [];
    }

    try {
        return JSON.parse(dataElement.textContent);
    } catch (error) {
        return [];
    }
}

function setupCabinGallery() {
    const gallery = document.querySelector("[data-cabin-gallery]");
    if (!gallery) {
        return;
    }

    const mainImage = gallery.querySelector(".cabin-main-image");
    const buttons = gallery.querySelectorAll(".thumb-button");

    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            if (button.classList.contains("is-active")) {
                return;
            }

            buttons.forEach((item) => item.classList.remove("is-active"));
            button.classList.add("is-active");
            mainImage.classList.add("is-changing");

            window.setTimeout(() => {
                mainImage.src = button.dataset.imageSrc;
                mainImage.alt = button.dataset.imageAlt;
                mainImage.classList.remove("is-changing");
            }, 180);
        });
    });
}

function setupLightbox() {
    const lightbox = document.getElementById("lightbox");
    if (!lightbox) {
        return;
    }

    const lightboxImage = lightbox.querySelector("img");
    const closeButton = lightbox.querySelector(".lightbox-close");

    document.querySelectorAll(".lightbox-image").forEach((image) => {
        image.addEventListener("click", () => {
            lightboxImage.src = image.src;
            lightboxImage.alt = image.alt;
            lightbox.classList.add("is-open");
            lightbox.setAttribute("aria-hidden", "false");
        });
    });

    const closeLightbox = () => {
        lightbox.classList.remove("is-open");
        lightbox.setAttribute("aria-hidden", "true");
        lightboxImage.src = "";
    };

    closeButton.addEventListener("click", closeLightbox);
    lightbox.addEventListener("click", (event) => {
        if (event.target === lightbox) {
            closeLightbox();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && lightbox.classList.contains("is-open")) {
            closeLightbox();
        }
    });
}

function setupFormValidation() {
    document.querySelectorAll("[data-validate-form], [data-inline-calendar-form]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            const checkIn = form.querySelector("[name='check_in']");
            const checkOut = form.querySelector("[name='check_out']");

            if (!checkIn || !checkOut) {
                return;
            }

            if (!checkIn.value || !checkOut.value) {
                event.preventDefault();
                alert("Оберіть дату заїзду та дату виїзду.");
                return;
            }

            if (new Date(checkOut.value) <= new Date(checkIn.value)) {
                event.preventDefault();
                alert("Дата виїзду має бути пізніше дати заїзду.");
            }
        });
    });
}

function setupRevealAnimations() {
    const elements = document.querySelectorAll(".reveal");

    if (!elements.length || !("IntersectionObserver" in window)) {
        elements.forEach((element) => element.classList.add("is-visible"));
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.16 }
    );

    elements.forEach((element) => observer.observe(element));
}
