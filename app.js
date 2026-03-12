document.addEventListener("DOMContentLoaded", () => {
  const banner = document.getElementById("cookie-banner");
  const acceptBtn = document.getElementById("cookie-accept");
  const declineBtn = document.getElementById("cookie-decline");

  if (!banner || !acceptBtn || !declineBtn) {
    console.warn("Cookie banner elements not found.");
    return;
  }

  const COOKIE_KEY = "tol_cookie_choice";

  function hideBanner() {
    banner.classList.remove("show");
    banner.setAttribute("aria-hidden", "true");
  }

  function showBanner() {
    banner.classList.add("show");
    banner.setAttribute("aria-hidden", "false");
  }

  function saveChoice(choice) {
    try {
      localStorage.setItem(COOKIE_KEY, choice);
    } catch (error) {
      console.error("Could not save cookie choice:", error);
    }
    hideBanner();
  }

  let existingChoice = null;

  try {
    existingChoice = localStorage.getItem(COOKIE_KEY);
  } catch (error) {
    console.error("Could not read cookie choice:", error);
  }

  if (!existingChoice) {
    showBanner();
  } else {
    hideBanner();
  }

  acceptBtn.addEventListener("click", () => {
    saveChoice("accepted");
  });

  declineBtn.addEventListener("click", () => {
    saveChoice("declined");
  });
});