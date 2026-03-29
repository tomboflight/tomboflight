(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  const familySelect = document.querySelector("[data-family-select]");
  const loadButton = document.querySelector("[data-load-intelligence]");
  const statMembers = document.querySelector("[data-stat-members]");
  const statRelations = document.querySelector("[data-stat-relations]");
  const statGenerations = document.querySelector("[data-stat-generations]");
  const statBranches = document.querySelector("[data-stat-branches]");
  const summaryBox = document.querySelector("[data-lineage-summary]");

  if (!familySelect || !loadButton || !summaryBox) {
    return;
  }

  function setSummaryState(message, type) {
    summaryBox.textContent = message;
    summaryBox.dataset.state = type || "info";
  }

  function setStat(node, value) {
    if (!node) return;
    node.textContent = String(value ?? "—");
  }

  function resetStats() {
    setStat(statMembers, "—");
    setStat(statRelations, "—");
    setStat(statGenerations, "—");
    setStat(statBranches, "—");
  }

  function renderSummary(details) {
    summaryBox.innerHTML = "";

    const paragraphOne = document.createElement("p");
    paragraphOne.textContent =
      "This lineage contains " +
      details.members +
      " recorded members connected through " +
      details.relationships +
      " relationships across " +
      details.generations +
      " generations.";

    const paragraphTwo = document.createElement("p");
    paragraphTwo.textContent =
      "Branch analysis detected " +
      details.branches +
      " parent-linked family branches in the current workspace.";

    summaryBox.appendChild(paragraphOne);
    summaryBox.appendChild(paragraphTwo);
    summaryBox.dataset.state = "success";
  }

  function computeBranchCount(members) {
    const branches = new Set();

    (members || []).forEach(function (member) {
      const fatherId = String(member && member.father_id ? member.father_id : "").trim();
      const motherId = String(member && member.mother_id ? member.mother_id : "").trim();

      if (fatherId) {
        branches.add("father:" + fatherId);
      }
      if (motherId) {
        branches.add("mother:" + motherId);
      }
    });

    return branches.size;
  }

  async function loadFamilies() {
    familySelect.disabled = true;
    familySelect.innerHTML = '<option value="">Loading families...</option>';
    setSummaryState("Loading available family workspaces...", "info");

    try {
      const families = await app.apiRequest("/families", { method: "GET" });

      familySelect.innerHTML = '<option value="">Select a family</option>';

      if (!Array.isArray(families) || !families.length) {
        familySelect.innerHTML =
          '<option value="">No family workspaces available</option>';
        resetStats();
        setSummaryState(
          "No family workspace is available for this account yet.",
          "error",
        );
        return;
      }

      families.forEach(function (family) {
        if (!family || !family.id) return;

        const option = document.createElement("option");
        option.value = family.id;
        option.textContent = family.family_name || family.id;
        familySelect.appendChild(option);
      });

      setSummaryState("Select a family to generate lineage intelligence.", "info");
    } catch (error) {
      familySelect.innerHTML =
        '<option value="">Unable to load families</option>';
      resetStats();
      setSummaryState(
        error && error.message
          ? error.message
          : "Unable to load family workspaces.",
        "error",
      );
    } finally {
      familySelect.disabled = false;
    }
  }

  async function analyzeFamily() {
    const familyId = String(familySelect.value || "").trim();

    if (!familyId) {
      setSummaryState("Select a family first.", "error");
      return;
    }

    loadButton.disabled = true;
    loadButton.textContent = "Analyzing...";
    setSummaryState("Analyzing lineage structure...", "info");

    try {
      const graph = await app.apiRequest(
        "/families/" + encodeURIComponent(familyId) + "/graph",
        { method: "GET" },
      );

      const members = Array.isArray(graph && graph.members) ? graph.members : [];
      const relationships = Array.isArray(graph && graph.relationships)
        ? graph.relationships
        : [];

      const generations = new Set();
      members.forEach(function (member) {
        const generation = Number(member && member.generation);
        if (Number.isFinite(generation)) {
          generations.add(generation);
        }
      });

      const summary = {
        members: members.length,
        relationships: relationships.length,
        generations: generations.size,
        branches: computeBranchCount(members),
      };

      setStat(statMembers, summary.members);
      setStat(statRelations, summary.relationships);
      setStat(statGenerations, summary.generations);
      setStat(statBranches, summary.branches);
      renderSummary(summary);
    } catch (error) {
      resetStats();
      setSummaryState(
        error && error.message
          ? error.message
          : "Unable to analyze this family workspace.",
        "error",
      );
    } finally {
      loadButton.disabled = false;
      loadButton.textContent = "Analyze Lineage";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const token = app.getToken ? app.getToken() : null;
    if (!token) {
      window.location.href = "signin.html";
      return;
    }

    loadButton.addEventListener("click", analyzeFamily);
    loadFamilies();
  });
})();
