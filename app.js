(function () {
  const header = document.querySelector(".site-header");
  const menuToggle = document.querySelector(".menu-toggle");
  const banner = document.querySelector("[data-cookie-banner]");
  const acceptBtns = document.querySelectorAll("[data-cookie-accept]");
  const declineBtns = document.querySelectorAll("[data-cookie-decline]");
  const statusEls = document.querySelectorAll("[data-cookie-status]");
  const storageKey = "tol_cookie_choice";
  const cookieName = "tol_cookie_choice";
  const cookieExpireDays = 365;
  const MS_PER_DAY = 86400000;

  /* ── Cookie helpers ── */

  function setCookie(name, value, days) {
    const expires = new Date(Date.now() + days * MS_PER_DAY);
    document.cookie =
      name + "=" + encodeURIComponent(value) +
      "; expires=" + expires.toUTCString() +
      "; path=/; SameSite=Lax";
  }

  function getCookieValue(name) {
    const match = document.cookie.match(
      new RegExp("(?:^|; )" + name + "=([^;]*)")
    );
    return match ? decodeURIComponent(match[1]) : null;
  }

  /* ── Status text ── */

  function setStatusText(value) {
    let message = "Your cookie preference has not been set yet.";

    if (value === "accepted") {
      message = "Optional analytics cookies are currently accepted on this device.";
    } else if (value === "declined") {
      message = "Optional analytics cookies are currently declined on this device.";
    }

    statusEls.forEach((el) => {
      el.textContent = message;
    });
  }

  /* ── Read / write preference (cookie + localStorage) ── */

  function getChoice() {
    try {
      return getCookieValue(cookieName) || localStorage.getItem(storageKey);
    } catch (error) {
      return getCookieValue(cookieName);
    }
  }

  function saveChoice(value) {
    setCookie(cookieName, value, cookieExpireDays);
    try {
      localStorage.setItem(storageKey, value);
    } catch (error) {
      /* no-op */
    }
    setStatusText(value);
    if (banner) {
      banner.classList.remove("visible");
    }
    if (value === "accepted") {
      initAnalytics();
    }
  }

  /* ── Analytics initialisation ── */

  function initAnalytics() {
    /* Placeholder: initialise your analytics SDK here when consent is given. */
  }

  /* ── Mobile menu ── */

  function closeMenu() {
    if (header) {
      header.classList.remove("open");
    }
    document.body.classList.remove("menu-open");
    if (menuToggle) {
      menuToggle.setAttribute("aria-expanded", "false");
    }
  }

  function toggleMenu() {
    if (!header) return;
    const isOpen = header.classList.toggle("open");
    document.body.classList.toggle("menu-open", isOpen);
    if (menuToggle) {
      menuToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }
  }

  if (menuToggle) {
    menuToggle.addEventListener("click", toggleMenu);
  }

  document.querySelectorAll(".site-nav a, .header-actions a").forEach((link) => {
    link.addEventListener("click", closeMenu);
  });

  /* ── Active link detection ── */

  const path = window.location.pathname;
  const currentPath = path.split("/").pop() || "index.html";

  document.querySelectorAll(".site-nav a").forEach((link) => {
    const href = link.getAttribute("href");
    if (
      href === currentPath ||
      (currentPath === "" && href === "index.html") ||
      (path === "/" && href === "index.html")
    ) {
      link.classList.add("active");
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });

  /* ── Cookie banner ── */

  const choice = getChoice();
  setStatusText(choice);

  if (!choice && banner) {
    banner.classList.add("visible");
  }

  if (choice === "accepted") {
    initAnalytics();
  }

  acceptBtns.forEach((btn) => {
    btn.addEventListener("click", function () {
      saveChoice("accepted");
    });
  });

  declineBtns.forEach((btn) => {
    btn.addEventListener("click", function () {
      saveChoice("declined");
    });
  });

  /* ── Keyboard: Escape closes menu ── */

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeMenu();
    }
  });
})();