document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const menuToggle = document.getElementById("menu-toggle");
  const mobileMenu = document.getElementById("mobile-menu");

  const cookieBanner = document.getElementById("cookie-banner");
  const acceptCookiesBtn = document.getElementById("accept-cookies");
  const declineCookiesBtn = document.getElementById("decline-cookies");
  const cookieStatusEls = document.querySelectorAll("[data-cookie-status]");

  const privacyForm = document.getElementById("privacy-choices-form");
  const dataRequestForm = document.getElementById("data-request-form");
  const signInForm = document.getElementById("signin-form");
  const signUpForm = document.getElementById("signup-form");

  const COOKIE_KEY = "tol_cookie_consent";
  const PRIVACY_KEY = "tol_privacy_choices";

  function setMenuState(isOpen) {
    if (!menuToggle || !mobileMenu) return;

    menuToggle.classList.toggle("active", isOpen);
    menuToggle.setAttribute("aria-expanded", String(isOpen));
    mobileMenu.classList.toggle("show", isOpen);
    body.classList.toggle("menu-open", isOpen);
  }

  if (menuToggle && mobileMenu) {
    menuToggle.addEventListener("click", () => {
      const isOpen = menuToggle.getAttribute("aria-expanded") === "true";
      setMenuState(!isOpen);
    });

    mobileMenu.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        setMenuState(false);
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        setMenuState(false);
      }
    });

    document.addEventListener("click", (event) => {
      const clickedInsideMenu = mobileMenu.contains(event.target);
      const clickedToggle = menuToggle.contains(event.target);

      if (!clickedInsideMenu && !clickedToggle) {
        setMenuState(false);
      }
    });
  }

  function updateCookieStatus(value) {
    cookieStatusEls.forEach((el) => {
      if (value === "accepted") {
        el.textContent = "Optional analytics cookies are enabled.";
      } else if (value === "declined") {
        el.textContent = "Optional analytics cookies are disabled.";
      } else {
        el.textContent = "Your cookie preference has not been set yet.";
      }
    });
  }

  function hideCookieBanner() {
    if (cookieBanner) {
      cookieBanner.classList.remove("show");
      cookieBanner.setAttribute("hidden", "hidden");
    }
  }

  function showCookieBanner() {
    if (cookieBanner) {
      cookieBanner.classList.add("show");
      cookieBanner.removeAttribute("hidden");
    }
  }

  const savedCookieConsent = localStorage.getItem(COOKIE_KEY);
  updateCookieStatus(savedCookieConsent);

  if (!savedCookieConsent) {
    showCookieBanner();
  } else {
    hideCookieBanner();
  }

  if (acceptCookiesBtn) {
    acceptCookiesBtn.addEventListener("click", () => {
      localStorage.setItem(COOKIE_KEY, "accepted");
      updateCookieStatus("accepted");
      hideCookieBanner();
    });
  }

  if (declineCookiesBtn) {
    declineCookiesBtn.addEventListener("click", () => {
      localStorage.setItem(COOKIE_KEY, "declined");
      updateCookieStatus("declined");
      hideCookieBanner();
    });
  }

  function loadPrivacyChoices() {
    try {
      const raw = localStorage.getItem(PRIVACY_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function savePrivacyChoices(data) {
    localStorage.setItem(PRIVACY_KEY, JSON.stringify(data));
  }

  if (privacyForm) {
    const analyticsField = document.getElementById("privacy-analytics");
    const gpcField = document.getElementById("privacy-gpc");
    const marketingField = document.getElementById("privacy-marketing");
    const privacyMessage = document.getElementById("privacy-choices-message");

    const existingChoices = loadPrivacyChoices();
    if (existingChoices) {
      if (analyticsField) analyticsField.checked = !!existingChoices.analytics;
      if (gpcField) gpcField.checked = !!existingChoices.gpc;
      if (marketingField) marketingField.checked = !!existingChoices.marketing;
    }

    privacyForm.addEventListener("submit", (event) => {
      event.preventDefault();

      const choiceData = {
        analytics: analyticsField ? analyticsField.checked : false,
        gpc: gpcField ? gpcField.checked : false,
        marketing: marketingField ? marketingField.checked : false,
        updatedAt: new Date().toISOString()
      };

      savePrivacyChoices(choiceData);

      if (choiceData.analytics) {
        localStorage.setItem(COOKIE_KEY, "accepted");
        updateCookieStatus("accepted");
      } else {
        localStorage.setItem(COOKIE_KEY, "declined");
        updateCookieStatus("declined");
      }

      if (privacyMessage) {
        privacyMessage.textContent =
          "Your privacy choices were saved on this device successfully.";
      }
    });
  }

  function showFormMessage(targetId, message, isError = false) {
    const el = document.getElementById(targetId);
    if (!el) return;

    el.textContent = message;
    el.style.color = isError ? "#ff8f8f" : "#9fe3bf";
  }

  if (dataRequestForm) {
    dataRequestForm.addEventListener("submit", (event) => {
      event.preventDefault();

      const fullName = document.getElementById("request-name")?.value.trim() || "";
      const email = document.getElementById("request-email")?.value.trim() || "";
      const requestType = document.getElementById("request-type")?.value || "";
      const details = document.getElementById("request-details")?.value.trim() || "";

      if (!fullName || !email || !requestType || !details) {
        showFormMessage(
          "data-request-message",
          "Please complete all required fields before submitting your request.",
          true
        );
        return;
      }

      const emailIsValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
      if (!emailIsValid) {
        showFormMessage(
          "data-request-message",
          "Please enter a valid email address.",
          true
        );
        return;
      }

      showFormMessage(
        "data-request-message",
        "Your request form is complete and ready to connect to your backend or email workflow."
      );

      dataRequestForm.reset();
    });
  }

  if (signInForm) {
    signInForm.addEventListener("submit", (event) => {
      event.preventDefault();

      const email = document.getElementById("signin-email")?.value.trim() || "";
      const password = document.getElementById("signin-password")?.value || "";

      if (!email || !password) {
        showFormMessage(
          "signin-message",
          "Please enter your email and password.",
          true
        );
        return;
      }

      const emailIsValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
      if (!emailIsValid) {
        showFormMessage(
          "signin-message",
          "Please enter a valid email address.",
          true
        );
        return;
      }

      showFormMessage(
        "signin-message",
        "Front-end sign-in check passed. Connect this form to your real authentication backend next."
      );
    });
  }

  if (signUpForm) {
    signUpForm.addEventListener("submit", (event) => {
      event.preventDefault();

      const fullName = document.getElementById("signup-name")?.value.trim() || "";
      const email = document.getElementById("signup-email")?.value.trim() || "";
      const password = document.getElementById("signup-password")?.value || "";
      const confirmPassword = document.getElementById("signup-confirm-password")?.value || "";
      const consent = document.getElementById("signup-consent")?.checked || false;

      if (!fullName || !email || !password || !confirmPassword) {
        showFormMessage(
          "signup-message",
          "Please complete all required fields.",
          true
        );
        return;
      }

      const emailIsValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
      if (!emailIsValid) {
        showFormMessage(
          "signup-message",
          "Please enter a valid email address.",
          true
        );
        return;
      }

      if (password.length < 8) {
        showFormMessage(
          "signup-message",
          "Your password must be at least 8 characters long.",
          true
        );
        return;
      }

      if (password !== confirmPassword) {
        showFormMessage(
          "signup-message",
          "Your passwords do not match.",
          true
        );
        return;
      }

      if (!consent) {
        showFormMessage(
          "signup-message",
          "You must confirm the consent and policy acknowledgment checkbox.",
          true
        );
        return;
      }

      showFormMessage(
        "signup-message",
        "Front-end sign-up check passed. Connect this form to your real registration backend next."
      );

      signUpForm.reset();
    });
  }

  const currentPath = window.location.pathname.split("/").pop() || "index.html";
  const navLinks = document.querySelectorAll("[data-nav-link]");
  navLinks.forEach((link) => {
    const href = link.getAttribute("href");
    if (
      href === currentPath ||
      (currentPath === "" && href === "index.html") ||
      (currentPath === "/" && href === "index.html")
    ) {
      link.classList.add("active");
    }
  });
});