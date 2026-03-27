(function () {
  "use strict";

  function getParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || "";
  }

  function humanize(value) {
    return String(value || "not_provided")
      .replaceAll("_", " ")
      .replaceAll("-", " ")
      .replace(/\b\w/g, function (char) {
        return char.toUpperCase();
      });
  }

  function nextStepMessage(type, packageCode) {
    const normalizedType = String(type || "")
      .trim()
      .toLowerCase();
    const normalizedPackage = String(packageCode || "")
      .trim()
      .toLowerCase();

    if (normalizedType === "maintenance") {
      return "Your maintenance subscription selection was received. Return to your dashboard for account access and package status.";
    }

    if (normalizedType === "addon" || normalizedType === "extra") {
      return "Your add-on purchase was received. It will be applied to the correct Tomb of Light project or package workflow.";
    }

    if (
      normalizedPackage === "legacy_snapshot" ||
      normalizedPackage === "legacy_portrait_intro" ||
      normalizedPackage === "digital_legacy_portrait"
    ) {
      return "Your portrait package purchase was received. Continue to your dashboard and upload your portrait and supporting records.";
    }

    if (
      normalizedPackage === "household_foundation" ||
      normalizedPackage === "heirloom_legacy_tree" ||
      normalizedPackage === "legacy_plus" ||
      normalizedPackage === "family_estate_concierge"
    ) {
      return "Your household or family package purchase was received. Continue to your dashboard to begin or continue your family build.";
    }

    if (normalizedPackage === "command_structure_network") {
      return "Your organizational package purchase was received. Continue to your dashboard to begin your command or leadership structure build.";
    }

    return "Your payment was received successfully. Continue to your dashboard for the next step.";
  }

  document.addEventListener("DOMContentLoaded", function () {
    const sessionNode = document.querySelector("[data-thank-you-session-id]");
    const typeNode = document.querySelector("[data-thank-you-type]");
    const packageNode = document.querySelector("[data-thank-you-package-code]");
    const nextStepNode = document.querySelector("[data-thank-you-next-step]");

    const sessionId = getParam("session_id");
    const type = getParam("type") || "package";
    const packageCode = getParam("package");

    if (sessionNode) {
      sessionNode.textContent = sessionId || "Not provided";
    }

    if (typeNode) {
      typeNode.textContent = humanize(type);
    }

    if (packageNode) {
      packageNode.textContent = packageCode || "Not provided";
    }

    if (nextStepNode) {
      nextStepNode.textContent = nextStepMessage(type, packageCode);
    }
  });
})();
