(function () {
  "use strict";

  const CASE_ACTION_HELP = {
    sync_package: "Reconcile the selected project's package identity with its authoritative package records.",
    repair_record: "Run the case-scoped repair workflow for inconsistencies already identified on this record.",
    queue_for_mint_review: "Move an eligible delivered project into governed Legacy Anchor review; this does not mint.",
    prepare_legacy_anchor: "Prepare the selected project's public-safe Legacy Anchor evidence for CEO review.",
    approve_legacy_anchor: "Record CEO final approval after every mint-readiness blocker is cleared.",
    queue_approved_legacy_anchor: "Queue an already approved Legacy Anchor for the controlled mint worker.",
    normalize_package: "Normalize package code/name/lane fields when legacy or inconsistent values are detected.",
    assign_lane: "Assign the correct production lane to the selected project when the lane is missing.",
    link_order_to_project: "Attach an authoritative paid order to its intended project; requires both records.",
    generate_entitlement: "Create the missing package entitlement from an authoritative acquisition record.",
    refresh_entitlement: "Recompute an existing entitlement so package capabilities match current truth.",
    run_readiness_check: "Read-only check of the selected project's current operational blockers and readiness.",
    refresh_case_data: "Reload the selected case from current backend records without changing business data.",
  };

  const BULK_ACTION_HELP = {
    "repair-missing-entitlements": "Repair eligible missing entitlements across the currently scoped queue.",
    "assign-missing-lanes": "Assign lanes only where authoritative package data makes the correct lane unambiguous.",
    "link-unlinked-paid-orders": "Link verified paid orders that have one safe, unambiguous project match.",
    "normalize-broken-package-records": "Normalize legacy package fields across safe records in the current scope.",
    "refresh-mint-readiness": "Recalculate mint readiness for eligible projects; this does not mint anything.",
    "repair-selected-records": "Run repair only against the records you explicitly checked in the case list.",
    "repair-all-safe-records": "Run only repairs classified by the backend as safe and unambiguous across the scoped queue.",
  };

  function decorateButtons() {
    document.querySelectorAll("[data-admin-case-action]").forEach(function (button) {
      const action = button.getAttribute("data-admin-case-action") || "";
      const help = CASE_ACTION_HELP[action] || "Governed case action. Review the selected case before execution.";
      button.setAttribute("data-action-help", help);
      button.setAttribute("aria-description", help);
      if (!button.title) button.title = help;
    });

    document.querySelectorAll("[data-admin-bulk-action]").forEach(function (button) {
      const action = button.getAttribute("data-admin-bulk-action") || "";
      const help = BULK_ACTION_HELP[action] || "Bulk operation. Confirm scope before execution.";
      button.setAttribute("data-action-help", help);
      button.setAttribute("aria-description", help);
      if (!button.title) button.title = help;
    });
  }

  function ensureSearchGuide() {
    const panel = document.querySelector(".admin-command-search");
    const input = document.querySelector("[data-admin-case-search]");
    if (!panel || !input || panel.querySelector(".admin-command-search-guide")) return;

    input.setAttribute("aria-keyshortcuts", "Meta+K Control+K /");
    input.setAttribute("autocomplete", "off");

    const guide = document.createElement("div");
    guide.className = "admin-command-search-guide";
    guide.id = "admin-case-search-help";
    guide.innerHTML =
      '<span><strong>Find → Open → Act:</strong> search by customer, email, project, family, order, session, wallet, token, or certificate. No customer record opens until you select it.</span>' +
      '<span><kbd class="admin-kbd">⌘K</kbd> / <kbd class="admin-kbd">Ctrl K</kbd> focus search</span>;
    panel.appendChild(guide);
  }

  function ensureCommandEmptyState() {
    const header = document.querySelector(".admin-case-workspace-header");
    if (!header || header.querySelector(".admin-case-command-empty")) return;
    const empty = document.createElement("div");
    empty.className = "admin-case-command-empty";
    empty.innerHTML =
      "<strong>No customer record is open.</strong> Search or choose a queue, then explicitly open a case. Case commands remain hidden until a target is selected.";
    header.appendChild(empty);
  }

  function syncSelectedCaseState() {
    const heading = document.querySelector("[data-admin-case-heading]");
    const panel = document.querySelector(".admin-case-workspace-panel");
    const closeButton = document.querySelector("[data-admin-clear-case]");
    if (!heading || !panel) return;

    const text = String(heading.textContent || "").trim().toLowerCase();
    const selected = Boolean(text && text !== "no case selected" && text !== "opening case workspace");
    panel.setAttribute("data-case-selected", selected ? "true" : "false");
    if (closeButton) closeButton.hidden = !selected;
  }

  function bindKeyboardSearch() {
    document.addEventListener("keydown", function (event) {
      const target = event.target;
      const editable = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || (target instanceof HTMLElement && target.isContentEditable);
      const commandK = (event.metaKey || event.ctrlKey) && String(event.key || "").toLowerCase() === "k";
      const slash = event.key === "/" && !editable && !event.metaKey && !event.ctrlKey && !event.altKey;
      if (!commandK && !slash) return;

      const input = document.querySelector("[data-admin-case-search]");
      if (!(input instanceof HTMLInputElement)) return;
      event.preventDefault();
      input.focus();
      input.select();
    });
  }

  function addOperatorContextStrip() {
    const commandCopy = document.querySelector(".admin-command-copy");
    if (!commandCopy || commandCopy.querySelector(".admin-operator-context-strip")) return;
    const strip = document.createElement("div");
    strip.className = "admin-operator-context-strip";
    strip.innerHTML =
      '<div><span>Operating model</span><strong>Search → select → act</strong></div>' +
      '<div><span>Customer privacy</span><strong>No default profile</strong></div>' +
      '<div><span>Writes</span><strong>Governed + audited</strong></div>' +
      '<div><span>Bulk work</span><strong>Separated from case work</strong></div>';
    commandCopy.appendChild(strip);
  }

  function observeCaseHeading() {
    const heading = document.querySelector("[data-admin-case-heading]");
    if (!heading) return;
    const observer = new MutationObserver(syncSelectedCaseState);
    observer.observe(heading, { childList: true, subtree: true, characterData: true });
  }

  function setup() {
    decorateButtons();
    ensureSearchGuide();
    ensureCommandEmptyState();
    addOperatorContextStrip();
    syncSelectedCaseState();
    observeCaseHeading();
    bindKeyboardSearch();

    const observer = new MutationObserver(function () {
      decorateButtons();
      syncSelectedCaseState();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup, { once: true });
  } else {
    setup();
  }
})();
