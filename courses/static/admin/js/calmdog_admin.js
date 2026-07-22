/* CalmDog administrace – přepínač filtrů na seznamech (changelist).
 *
 * Přidá nad tabulku tlačítko „Filtry", které schová/zobrazí pravý filtrovací
 * panel (#changelist-filter). Ve výchozím stavu je filtr zarolovaný, takže se
 * do tabulky vejdou všechny sloupce. Stav se pamatuje per-stránka v localStorage.
 */
(function () {
    "use strict";

    function init() {
        var changelist = document.getElementById("changelist");
        var filter = document.getElementById("changelist-filter");
        if (!changelist || !filter) {
            return; // stránka bez filtrů – nic nedělat
        }

        var storageKey = "cd-filters-collapsed:" + window.location.pathname;

        // Výchozí = zabaleno; rozbalí se jen pokud si to uživatel dřív vybral.
        var collapsed = true;
        try {
            var stored = window.localStorage.getItem(storageKey);
            if (stored === "0") {
                collapsed = false;
            }
        } catch (e) { /* localStorage může být nedostupný – ignorovat */ }

        var caret =
            '<svg class="cd-filters-toggle__caret" viewBox="0 0 20 20" fill="none" ' +
            'aria-hidden="true"><path d="M6 8l4 4 4-4" stroke="currentColor" ' +
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        var icon =
            '<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path ' +
            'd="M3 5h14M6 10h8M9 15h2" stroke="currentColor" stroke-width="2" ' +
            'stroke-linecap="round"/></svg>';

        var toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "cd-filters-toggle";
        toggle.innerHTML = icon + '<span class="cd-filters-toggle__label">Filtry</span>' + caret;

        function apply() {
            changelist.classList.toggle("cd-filters-collapsed", collapsed);
            toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
        }

        toggle.addEventListener("click", function () {
            collapsed = !collapsed;
            try {
                window.localStorage.setItem(storageKey, collapsed ? "1" : "0");
            } catch (e) { /* ignorovat */ }
            apply();
        });

        // Tlačítko umístit nad tabulku – nejlépe do panelu akcí, jinak na začátek
        // changelist-formu, případně před samotný changelist.
        var actions = changelist.querySelector(".actions");
        var form = document.getElementById("changelist-form");
        if (actions && actions.parentNode) {
            actions.parentNode.insertBefore(toggle, actions);
        } else if (form) {
            form.insertBefore(toggle, form.firstChild);
        } else {
            changelist.insertBefore(toggle, changelist.firstChild);
        }

        apply();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
