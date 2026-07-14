/* Našeptávač adres (Mapy.cz Suggest API) – progresivní vylepšení.
   Aktivuje se jen na polích s [data-address-suggest], jen pokud je nastavený
   API klíč (data-mapy-api-key na <body>). Bez klíče/při chybě sítě zůstává
   pole běžný textový input – nic se nerozbije. */
(function () {
  "use strict";

  function debounce(fn, delay) {
    let timer = null;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function municipalityName(item) {
    const structure = item.regionalStructure || [];
    const muni = structure.find((r) => r.type === "regional.municipality");
    return muni ? muni.name : "";
  }

  function initField(input, apiKey) {
    const cityTarget = input.dataset.cityTarget ? document.getElementById(input.dataset.cityTarget) : null;
    const zipTarget = input.dataset.zipTarget ? document.getElementById(input.dataset.zipTarget) : null;

    // Dropdown je position:absolute vůči nejbližšímu positioned předkovi –
    // zajistíme, že je jím přímo obal inputu, ať se nevykreslí jinam na stránce.
    if (input.parentElement && getComputedStyle(input.parentElement).position === "static") {
      input.parentElement.style.position = "relative";
    }

    const box = document.createElement("ul");
    box.className = "address-suggest-list";
    box.setAttribute("role", "listbox");
    box.hidden = true;
    box.id = "address-suggest-" + Math.random().toString(36).slice(2, 9);
    input.insertAdjacentElement("afterend", box);

    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", box.id);
    input.setAttribute("autocomplete", "off");

    let items = [];
    let activeIndex = -1;
    let controller = null;

    function closeBox() {
      box.hidden = true;
      box.innerHTML = "";
      items = [];
      activeIndex = -1;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    }

    function selectItem(item) {
      input.value = item.name;
      if (cityTarget) cityTarget.value = municipalityName(item);
      if (zipTarget && item.zip) zipTarget.value = item.zip;
      closeBox();
    }

    function highlight(index) {
      const options = box.querySelectorAll(".address-suggest-item");
      options.forEach((el) => {
        el.classList.remove("is-active");
        el.setAttribute("aria-selected", "false");
      });
      if (index >= 0 && options[index]) {
        options[index].classList.add("is-active");
        options[index].setAttribute("aria-selected", "true");
        input.setAttribute("aria-activedescendant", options[index].id);
        options[index].scrollIntoView({ block: "nearest" });
      } else {
        input.removeAttribute("aria-activedescendant");
      }
      activeIndex = index;
    }

    function renderItems(newItems) {
      items = newItems;
      box.innerHTML = "";
      if (!items.length) {
        closeBox();
        return;
      }
      items.forEach((item, index) => {
        const li = document.createElement("li");
        li.className = "address-suggest-item";
        li.id = box.id + "-opt-" + index;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");

        const main = document.createElement("span");
        main.className = "address-suggest-item-main";
        main.textContent = item.name;

        const sub = document.createElement("span");
        sub.className = "address-suggest-item-sub";
        sub.textContent = item.location || "";

        li.appendChild(main);
        li.appendChild(sub);
        // mousedown (ne click) – proběhne dřív než blur inputu, výběr tak funguje
        li.addEventListener("mousedown", (e) => {
          e.preventDefault();
          selectItem(item);
        });
        box.appendChild(li);
      });
      box.hidden = false;
      input.setAttribute("aria-expanded", "true");
      activeIndex = -1;
    }

    const fetchSuggestions = debounce((query) => {
      if (controller) controller.abort();
      controller = new AbortController();

      const url = new URL("https://api.mapy.com/v1/suggest");
      url.searchParams.set("apikey", apiKey);
      url.searchParams.set("query", query);
      url.searchParams.set("lang", "cs");
      url.searchParams.set("limit", "5");
      url.searchParams.append("type", "regional.address");
      url.searchParams.append("locality", "cz");

      fetch(url, { signal: controller.signal })
        .then((res) => (res.ok ? res.json() : Promise.reject()))
        .then((data) => renderItems(data.items || []))
        .catch(() => {
          /* tichý fallback – pole zůstává běžný text input */
        });
    }, 300);

    input.addEventListener("input", () => {
      const query = input.value.trim();
      if (query.length < 3) {
        closeBox();
        return;
      }
      fetchSuggestions(query);
    });

    input.addEventListener("keydown", (e) => {
      if (box.hidden) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        highlight(Math.min(activeIndex + 1, items.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        highlight(Math.max(activeIndex - 1, 0));
      } else if (e.key === "Enter") {
        if (activeIndex >= 0 && items[activeIndex]) {
          e.preventDefault();
          selectItem(items[activeIndex]);
        }
      } else if (e.key === "Escape") {
        closeBox();
      }
    });

    input.addEventListener("blur", () => {
      setTimeout(closeBox, 100);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const apiKey = document.body?.dataset?.mapyApiKey || "";
    if (!apiKey) return;

    document.querySelectorAll("[data-address-suggest]").forEach((input) => {
      initField(input, apiKey);
    });
  });
})();
