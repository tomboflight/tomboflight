(function () {
  const header = document.querySelector(".site-header");
  const menuToggle = document.querySelector(".menu-toggle");
  const banner = document.querySelector("[data-cookie-banner]");
  const acceptBtns = document.querySelectorAll("[data-cookie-accept]");
  const declineBtns = document.querySelectorAll("[data-cookie-decline]");
  const statusEls = document.querySelectorAll("[data-cookie-status]");
  const storageKey = "tol_cookie_choice";

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

  function getChoice() {
    try {
      return localStorage.getItem(storageKey);
    } catch (error) {
      return null;
    }
  }

  function saveChoice(value) {
    try {
      localStorage.setItem(storageKey, value);
    } catch (error) {
      /* no-op */
    }
    setStatusText(value);
    if (banner) {
      banner.classList.remove("visible");
    }
  }

  function closeMenu() {
    if (header) {
      header.classList.remove("open");
    }
    document.body.classList.remove("menu-open");
  }

  function toggleMenu() {
    if (!header) return;
    const isOpen = header.classList.toggle("open");
    document.body.classList.toggle("menu-open", isOpen);
  }

  if (menuToggle) {
    menuToggle.addEventListener("click", toggleMenu);
  }

  document.querySelectorAll(".site-nav a, .header-actions a").forEach((link) => {
    link.addEventListener("click", closeMenu);
  });

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
    }
  });

  const choice = getChoice();
  setStatusText(choice);

  if (!choice && banner) {
    banner.classList.add("visible");
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

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeMenu();
    }
  });
})();