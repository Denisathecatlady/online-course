(function () {
  var CONSENT_KEY = "cookieConsent";
  var VERSION_KEY = "cookieConsentVersion";

  // ── Migrace ze starého klíče ─────────────────────────────────────────────
  // Uživatelé, kteří klikli na starý banner „Rozumím" (cookiesAccepted=true),
  // dostanou souhlas bez analytiky – banner se jim nezobrazí znovu.
  var oldKey = "cookiesAccepted";
  if (localStorage.getItem(oldKey) !== null && localStorage.getItem(CONSENT_KEY) === null) {
    var wasAccepted = localStorage.getItem(oldKey) === "true";
    localStorage.setItem(CONSENT_KEY, wasAccepted ? "rejected" : "rejected"); // starý banner nebyl souhlas s analytikou
    localStorage.removeItem(oldKey);
  }

  // ── Kontrola verze souhlasu ──────────────────────────────────────────────
  // Pokud se verze v kódu liší od uložené, souhlas se zruší a banner se ukáže.
  var currentVersion = document.querySelector('meta[name="cookie-consent-version"]')?.getAttribute("content") || "1";
  var storedVersion  = localStorage.getItem(VERSION_KEY);

  if (storedVersion !== null && storedVersion !== currentVersion) {
    localStorage.removeItem(CONSENT_KEY);
    localStorage.removeItem(VERSION_KEY);
  }

  var consent = localStorage.getItem(CONSENT_KEY);

  // ── Banner ───────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    var banner = document.getElementById("cookie-banner");
    if (!banner) return;

    if (consent !== null) {
      banner.style.display = "none";
      return;
    }

    document.getElementById("accept-cookies")?.addEventListener("click", function () {
      localStorage.setItem(CONSENT_KEY, "accepted");
      localStorage.setItem(VERSION_KEY, currentVersion);
      banner.style.display = "none";
      window.calmDogLoadAnalytics?.();
    });

    document.getElementById("reject-cookies")?.addEventListener("click", function () {
      localStorage.setItem(CONSENT_KEY, "rejected");
      localStorage.setItem(VERSION_KEY, currentVersion);
      banner.style.display = "none";
    });
  });
})();
