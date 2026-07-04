(function () {
  var KEY = "cookieConsent";
  var consent = localStorage.getItem(KEY);

  document.addEventListener("DOMContentLoaded", function () {
    var banner = document.getElementById("cookie-banner");
    if (!banner) return;

    // Rozhodnutí je uloženo – banner skrýt
    if (consent !== null) {
      banner.style.display = "none";
      return;
    }

    // Přijmout vše – načíst GTM a uložit souhlas
    document.getElementById("accept-cookies")?.addEventListener("click", function () {
      localStorage.setItem(KEY, "accepted");
      banner.style.display = "none";
      window.calmDogLoadAnalytics?.();
    });

    // Jen nezbytné – uložit odmítnutí, GTM se nenačte
    document.getElementById("reject-cookies")?.addEventListener("click", function () {
      localStorage.setItem(KEY, "rejected");
      banner.style.display = "none";
    });
  });
})();
