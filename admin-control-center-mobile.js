(function () {
  "use strict";

  const MOBILE_CONTROL_CENTER = "(max-width: 1180px)";

  function setupMobileOperationsRail() {
    const rail = document.querySelector(".admin-case-rail[data-mobile-nav]");
    const toggle = document.querySelector("[data-admin-rail-toggle]");
    const toggleLabel = document.querySelector("[data-admin-rail-toggle-label]");
    const navigation = document.querySelector("#admin-operations-navigation");
    const caseCenter = document.querySelector(".admin-case-center");

    if (!rail || !toggle || !navigation) return;

    const viewport = window.matchMedia(MOBILE_CONTROL_CENTER);

    function setExpanded(expanded) {
      const isMobile = viewport.matches;
      const shouldExpand = isMobile ? Boolean(expanded) : true;

      rail.dataset.mobileNav = shouldExpand ? "expanded" : "collapsed";
      toggle.setAttribute("aria-expanded", shouldExpand ? "true" : "false");
      navigation.setAttribute("aria-hidden", isMobile && !shouldExpand ? "true" : "false");
      if (toggleLabel) {
        toggleLabel.textContent = shouldExpand ? "Close operations" : "Browse operations";
      }
    }

    function syncViewport() {
      setExpanded(!viewport.matches);
    }

    toggle.addEventListener("click", function () {
      const expanded = toggle.getAttribute("aria-expanded") === "true";
      setExpanded(!expanded);
    });

    navigation.querySelectorAll("details").forEach(function (group) {
      group.addEventListener("toggle", function () {
        if (!viewport.matches || !group.open) return;
        navigation.querySelectorAll("details[open]").forEach(function (openGroup) {
          if (openGroup !== group) openGroup.open = false;
        });
      });
    });

    navigation.addEventListener("click", function (event) {
      const target = event.target;
      if (!(target instanceof Element) || !target.closest("[data-case-queue]") || !viewport.matches) {
        return;
      }

      setExpanded(false);
      toggle.focus({ preventScroll: true });
      if (caseCenter) {
        window.requestAnimationFrame(function () {
          caseCenter.scrollIntoView({ block: "start", behavior: "auto" });
        });
      }
    });

    if (typeof viewport.addEventListener === "function") {
      viewport.addEventListener("change", syncViewport);
    } else if (typeof viewport.addListener === "function") {
      viewport.addListener(syncViewport);
    }

    window.addEventListener("pageshow", syncViewport);
    syncViewport();
  }

  document.addEventListener("DOMContentLoaded", setupMobileOperationsRail);
})();
