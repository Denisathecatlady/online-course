document.addEventListener("DOMContentLoaded", () => {
    const banner = document.getElementById("cookie-banner");
    const accepted = localStorage.getItem("cookiesAccepted");

    if (accepted) {
        banner.style.display = "none";
    }

    document.getElementById("accept-cookies")?.addEventListener("click", () => {
        localStorage.setItem("cookiesAccepted", "true");
        banner.style.display = "none";
    });

    document.getElementById("reject-cookies")?.addEventListener("click", () => {
        localStorage.setItem("cookiesAccepted", "false");
        banner.style.display = "none";
    });
});
