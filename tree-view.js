(function () {
  "use strict";

  const ANCESTRY_TYPES = new Set([
    "parent_child",
    "adoptive_parent_child",
    "step_parent_child",
  ]);

  const PRIMARY_ANCESTRY_TYPES = new Set([
    "parent_child",
    "adoptive_parent_child",
  ]);

  const SECONDARY_ANCESTRY_TYPES = new Set(["step_parent_child"]);

  const TREE_VIEW_STATE = {
    scale: 1,
    minScale: 0.42,
    maxScale: 1.9,
    step: 0.1,
    viewport: null,
    sceneSizer: null,
    stage: null,
    wrapperWidth: 0,
    wrapperHeight: 0,
    zoomLabel: null,
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function showStatus(node, message, type) {
    if (!node) return;

    node.style.display = "block";
    node.textContent = message;
    node.style.color =
      type === "error" ? "#ffb3b3" : type === "success" ? "#cfe8cf" : "#d6e6ff";
  }

  function hideStatus(node) {
    if (!node) return;
    node.style.display = "none";
    node.textContent = "";
  }

  function clearDetailPanel(detailPanel, detailEmpty) {
    if (detailPanel) {
      detailPanel.style.display = "none";
      detailPanel.innerHTML = "";
    }

    if (detailEmpty) {
      detailEmpty.style.display = "block";
    }
  }

  function getDisplayName(member) {
    return (
      member?.display_name ||
      `${member?.first_name || ""} ${member?.last_name || ""}`.trim() ||
      "Unknown"
    );
  }

  function getBirthYear(member) {
    return member?.birth_year ? String(member.birth_year) : "Unknown";
  }

  function getVerificationLabel(member) {
    if (member?.verification_status) {
      return String(member.verification_status).replaceAll("_", " ");
    }
    return member?.is_verified ? "verified" : "not verified";
  }

  function formatRelationshipLabel(relationshipType, context) {
    const rel = String(relationshipType || "")
      .trim()
      .toLowerCase();

    if (context === "parents") {
      if (rel === "parent_child") return "biological parent";
      if (rel === "step_parent_child") return "step-parent";
      if (rel === "adoptive_parent_child") return "adoptive parent";
      return rel.replaceAll("_", " ");
    }

    if (context === "children") {
      if (rel === "parent_child") return "biological child";
      if (rel === "step_parent_child") return "step-child";
      if (rel === "adoptive_parent_child") return "adopted child";
      return rel.replaceAll("_", " ");
    }

    if (context === "spouses") {
      return "spouse";
    }

    return rel.replaceAll("_", " ");
  }

  async function setupTreeViewPage() {
    if (!window.TOLAuth) return;

    const page = document.querySelector("[data-tree-view-page]");
    if (!page) return;

    const familySelect = document.querySelector("[data-tree-family-select]");
    const statusNode = document.querySelector("[data-tree-status]");
    const canvas = document.querySelector("[data-tree-canvas]");
    const loadBtn = document.querySelector("[data-load-tree-btn]");
    const detailPanel = document.querySelector("[data-tree-detail]");
    const detailEmpty = document.querySelector("[data-tree-detail-empty]");

    const token = window.TOLAuth.getToken();
    if (!token) {
      window.location.href = "signin.html";
      return;
    }

    try {
      await window.TOLAuth.apiRequest("/auth/me", { method: "GET" });
    } catch (error) {
      window.TOLAuth.clearSession();
      window.location.href = "signin.html";
      return;
    }

    await loadFamilyOptions(familySelect, statusNode);

    if (loadBtn) {
      loadBtn.addEventListener("click", async function () {
        const familyId = familySelect ? familySelect.value : "";
        if (!familyId) {
          showStatus(statusNode, "Please select a family first.", "error");
          return;
        }

        clearDetailPanel(detailPanel, detailEmpty);
        await loadAndRenderTree(
          familyId,
          canvas,
          statusNode,
          detailPanel,
          detailEmpty,
        );
      });
    }

    if (familySelect) {
      familySelect.addEventListener("change", function () {
        hideStatus(statusNode);
      });
    }
  }

  async function loadFamilyOptions(selectNode, statusNode) {
    if (!selectNode || !window.TOLAuth) return;

    selectNode.innerHTML = '<option value="">Loading families...</option>';

    try {
      const families = await window.TOLAuth.apiRequest("/families", {
        method: "GET",
      });

      if (!Array.isArray(families) || families.length === 0) {
        selectNode.innerHTML =
          '<option value="">No families available</option>';
        showStatus(
          statusNode,
          "No families were found for this account.",
          "error",
        );
        return;
      }

      selectNode.innerHTML = '<option value="">Select a family</option>';

      families.forEach(function (family) {
        const option = document.createElement("option");
        option.value = family.id;
        option.textContent = `${family.family_name} (${family.created_by})`;
        selectNode.appendChild(option);
      });

      if (families.length === 1) {
        selectNode.value = families[0].id;
      }

      hideStatus(statusNode);
    } catch (error) {
      selectNode.innerHTML = '<option value="">No families available</option>';
      showStatus(
        statusNode,
        error.message || "Unable to load families for this account.",
        "error",
      );
    }
  }

  async function loadAndRenderTree(
    familyId,
    canvas,
    statusNode,
    detailPanel,
    detailEmpty,
  ) {
    if (!canvas || !window.TOLAuth) return;

    showStatus(statusNode, "Loading visual tree...", "info");
    canvas.innerHTML = "";

    try {
      const graph = await window.TOLAuth.apiRequest(
        `/families/${familyId}/graph`,
        {
          method: "GET",
        },
      );

      renderStructuredTree(graph, canvas, detailPanel, detailEmpty);
      showStatus(
        statusNode,
        "Visual family tree loaded successfully. Use the zoom controls for larger families.",
        "success",
      );
    } catch (error) {
      console.error("Tree render error:", error);
      showStatus(statusNode, error.message || "Failed to load tree.", "error");
    }
  }

  function renderStructuredTree(graph, canvas, detailPanel, detailEmpty) {
    const members = Array.isArray(graph.members) ? graph.members : [];
    const relationships = Array.isArray(graph.relationships)
      ? graph.relationships
      : [];

    if (!members.length) {
      canvas.innerHTML =
        '<div class="tree-empty">No members found for this family.</div>';
      return;
    }

    const memberMap = new Map();
    members.forEach((member) => memberMap.set(member.id, member));

    const spousePairs = buildSpousePairs(relationships);
    const pairMap = new Map();
    spousePairs.forEach((pair) => {
      pairMap.set(pair.a, pair);
      pairMap.set(pair.b, pair);
    });

    const memberRowMap = buildMemberRowMap(members, relationships);

    const generationGroups = new Map();
    members.forEach((member) => {
      const rowIndex = memberRowMap.get(member.id) ?? 0;
      if (!generationGroups.has(rowIndex)) generationGroups.set(rowIndex, []);
      generationGroups.get(rowIndex).push(member);
    });

    const sortedRows = Array.from(generationGroups.keys()).sort(
      (a, b) => a - b,
    );

    const nodeWidth = 190;
    const nodeHeight = 104;
    const coupleGap = 28;
    const itemGap = 80;
    const rowGap = 200;
    const leftPadding = 170;
    const rightPadding = 110;
    const topPadding = 70;

    const rows = [];
    const placedIds = new Set();

    sortedRows.forEach((rowIndex, visualRowIndex) => {
      const rowMembers = generationGroups.get(rowIndex) || [];
      const rowItems = [];

      rowMembers.forEach((member) => {
        if (placedIds.has(member.id)) return;

        const pair = pairMap.get(member.id);
        if (pair) {
          const spouseA = memberMap.get(pair.a);
          const spouseB = memberMap.get(pair.b);

          if (spouseA && spouseB) {
            rowItems.push({
              type: "couple",
              members: orderCouple(spouseA, spouseB),
            });
            placedIds.add(spouseA.id);
            placedIds.add(spouseB.id);
            return;
          }
        }

        rowItems.push({
          type: "single",
          members: [member],
        });
        placedIds.add(member.id);
      });

      rows.push({ rowIndex, visualRowIndex, items: rowItems });
    });

    const maxRowWidth = rows.reduce((maxWidth, row) => {
      const width = row.items.reduce((sum, item, index) => {
        const itemWidth =
          item.type === "couple" ? nodeWidth * 2 + coupleGap : nodeWidth;
        return sum + itemWidth + (index > 0 ? itemGap : 0);
      }, 0);
      return Math.max(maxWidth, width);
    }, 0);

    const width = Math.max(1500, leftPadding + maxRowWidth + rightPadding);
    const height = Math.max(
      760,
      topPadding * 2 + sortedRows.length * rowGap + 180,
    );

    const shell = document.createElement("div");
    shell.style.display = "grid";
    shell.style.gap = "0.9rem";

    const toolbar = document.createElement("div");
    toolbar.className = "tree-toolbar";

    const zoomOutBtn = document.createElement("button");
    zoomOutBtn.type = "button";
    zoomOutBtn.className = "btn btn-secondary";
    zoomOutBtn.textContent = "Zoom Out";

    const zoomInBtn = document.createElement("button");
    zoomInBtn.type = "button";
    zoomInBtn.className = "btn btn-secondary";
    zoomInBtn.textContent = "Zoom In";

    const zoomResetBtn = document.createElement("button");
    zoomResetBtn.type = "button";
    zoomResetBtn.className = "btn btn-secondary";
    zoomResetBtn.textContent = "Reset";

    const zoomFitBtn = document.createElement("button");
    zoomFitBtn.type = "button";
    zoomFitBtn.className = "btn btn-primary";
    zoomFitBtn.textContent = "Fit to View";

    const viewFamiliesBtn = document.createElement("a");
    viewFamiliesBtn.className = "btn btn-secondary";
    viewFamiliesBtn.href = "dashboard.html";
    viewFamiliesBtn.textContent = "View Families";

    const zoomLabel = document.createElement("span");
    zoomLabel.className = "tree-zoom-label";
    zoomLabel.textContent = "100%";

    toolbar.appendChild(zoomOutBtn);
    toolbar.appendChild(zoomInBtn);
    toolbar.appendChild(zoomResetBtn);
    toolbar.appendChild(zoomFitBtn);
    toolbar.appendChild(viewFamiliesBtn);
    toolbar.appendChild(zoomLabel);

    const viewport = document.createElement("div");
    viewport.className = "tree-viewport";

    const sceneSizer = document.createElement("div");
    sceneSizer.style.position = "relative";
    sceneSizer.style.width = `${width}px`;
    sceneSizer.style.height = `${height}px`;

    const stage = document.createElement("div");
    stage.style.position = "absolute";
    stage.style.left = "0";
    stage.style.top = "0";
    stage.style.transformOrigin = "top left";

    const wrapper = document.createElement("div");
    wrapper.className = "tree-wrapper";
    wrapper.style.width = `${width}px`;
    wrapper.style.height = `${height}px`;

    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("class", "tree-lines");
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

    const positions = new Map();

    const primaryRelationships = relationships.filter((rel) =>
      PRIMARY_ANCESTRY_TYPES.has(rel.relationship_type),
    );

    rows.forEach((row) => {
      const y = topPadding + row.visualRowIndex * rowGap;

      const label = document.createElement("div");
      label.className = "tree-generation-label";
      label.style.left = "24px";
      label.style.top = `${y + 26}px`;
      label.textContent = `Generation ${row.rowIndex}`;
      wrapper.appendChild(label);

      const enrichedItems = row.items.map((item) => {
        const anchorX = getItemAnchorX(
          item,
          positions,
          primaryRelationships,
          pairMap,
        );
        const widthValue =
          item.type === "couple" ? nodeWidth * 2 + coupleGap : nodeWidth;

        return {
          ...item,
          anchorX,
          itemWidth: widthValue,
        };
      });

      enrichedItems.sort((a, b) => {
        const aHasAnchor = Number.isFinite(a.anchorX);
        const bHasAnchor = Number.isFinite(b.anchorX);

        if (aHasAnchor && bHasAnchor && a.anchorX !== b.anchorX) {
          return a.anchorX - b.anchorX;
        }
        if (aHasAnchor && !bHasAnchor) return -1;
        if (!aHasAnchor && bHasAnchor) return 1;

        const aName = getItemSortName(a);
        const bName = getItemSortName(b);
        return aName.localeCompare(bName);
      });

      const rowWidth = enrichedItems.reduce((sum, item, index) => {
        return sum + item.itemWidth + (index > 0 ? itemGap : 0);
      }, 0);

      let currentX =
        leftPadding + (width - leftPadding - rightPadding - rowWidth) / 2;

      enrichedItems.forEach((item) => {
        if (item.type === "single") {
          const member = item.members[0];
          placeMemberNode(
            wrapper,
            member,
            currentX,
            y,
            nodeWidth,
            nodeHeight,
            detailPanel,
            detailEmpty,
            memberMap,
            relationships,
          );
          positions.set(
            member.id,
            buildPosition(currentX, y, nodeWidth, nodeHeight),
          );
          currentX += nodeWidth + itemGap;
        } else {
          const [leftMember, rightMember] = item.members;

          placeMemberNode(
            wrapper,
            leftMember,
            currentX,
            y,
            nodeWidth,
            nodeHeight,
            detailPanel,
            detailEmpty,
            memberMap,
            relationships,
          );
          positions.set(
            leftMember.id,
            buildPosition(currentX, y, nodeWidth, nodeHeight),
          );

          const rightX = currentX + nodeWidth + coupleGap;

          placeMemberNode(
            wrapper,
            rightMember,
            rightX,
            y,
            nodeWidth,
            nodeHeight,
            detailPanel,
            detailEmpty,
            memberMap,
            relationships,
          );
          positions.set(
            rightMember.id,
            buildPosition(rightX, y, nodeWidth, nodeHeight),
          );

          svg.appendChild(
            makeCurvedLine(
              svgNS,
              positions.get(leftMember.id).centerX,
              positions.get(leftMember.id).centerY,
              positions.get(rightMember.id).centerX,
              positions.get(rightMember.id).centerY,
              "tree-line spouse",
            ),
          );

          currentX += nodeWidth * 2 + coupleGap + itemGap;
        }
      });
    });

    const childLinks = primaryRelationships;
    const spouseLinks = relationships.filter(
      (rel) => rel.relationship_type === "spouse",
    );

    const spouseSet = new Set(
      spouseLinks.map((rel) =>
        buildPairKey(rel.source_member_id, rel.target_member_id),
      ),
    );

    const groupedChildren = new Map();
    const soloParents = [];

    const childrenByTarget = new Map();
    childLinks.forEach((rel) => {
      if (!childrenByTarget.has(rel.target_member_id)) {
        childrenByTarget.set(rel.target_member_id, []);
      }
      childrenByTarget.get(rel.target_member_id).push(rel.source_member_id);
    });

    childrenByTarget.forEach((parents, childId) => {
      const uniqueParents = [...new Set(parents)].filter(Boolean);

      if (uniqueParents.length >= 2) {
        const paired = findPairedParents(uniqueParents, spouseSet);
        if (paired) {
          const key = `${paired[0]}::${paired[1]}::${childId}`;
          groupedChildren.set(key, {
            parentA: paired[0],
            parentB: paired[1],
            childId,
          });
          return;
        }
      }

      uniqueParents.forEach((parentId) => {
        soloParents.push({ parentId, childId });
      });
    });

    groupedChildren.forEach((link) => {
      const parentAPos = positions.get(link.parentA);
      const parentBPos = positions.get(link.parentB);
      const childPos = positions.get(link.childId);

      if (!parentAPos || !parentBPos || !childPos) return;

      const coupleCenterX = (parentAPos.centerX + parentBPos.centerX) / 2;
      const coupleBottomY = Math.max(parentAPos.bottomY, parentBPos.bottomY);
      const childTopY = childPos.topY;

      const branchTopY = coupleBottomY + 22;
      const branchBottomY = childTopY - 18;

      svg.appendChild(
        makeVerticalLine(
          svgNS,
          coupleCenterX,
          coupleBottomY,
          branchTopY,
          "tree-line parent-child",
        ),
      );
      svg.appendChild(
        makeCurvedLine(
          svgNS,
          coupleCenterX,
          branchTopY,
          childPos.centerX,
          branchBottomY,
          "tree-line parent-child",
        ),
      );
      svg.appendChild(
        makeVerticalLine(
          svgNS,
          childPos.centerX,
          branchBottomY,
          childTopY,
          "tree-line parent-child",
        ),
      );
    });

    const groupedChildIds = new Set(
      Array.from(groupedChildren.values())
        .map((link) => `${link.parentA}::${link.childId}`)
        .concat(
          Array.from(groupedChildren.values()).map(
            (link) => `${link.parentB}::${link.childId}`,
          ),
        ),
    );

    soloParents.forEach((link) => {
      if (groupedChildIds.has(`${link.parentId}::${link.childId}`)) return;

      const parentPos = positions.get(link.parentId);
      const childPos = positions.get(link.childId);
      if (!parentPos || !childPos) return;

      svg.appendChild(
        makeCurvedLine(
          svgNS,
          parentPos.centerX,
          parentPos.bottomY,
          childPos.centerX,
          childPos.topY,
          "tree-line parent-child",
        ),
      );
    });

    const stepParentLinks = relationships.filter((rel) =>
      SECONDARY_ANCESTRY_TYPES.has(rel.relationship_type),
    );

    stepParentLinks.forEach((rel) => {
      const parentPos = positions.get(rel.source_member_id);
      const childPos = positions.get(rel.target_member_id);
      if (!parentPos || !childPos) return;

      const dashed = makeCurvedLine(
        svgNS,
        parentPos.centerX,
        parentPos.bottomY,
        childPos.centerX,
        childPos.topY,
        "tree-line parent-child",
      );
      dashed.style.strokeDasharray = "8 8";
      dashed.style.opacity = "0.7";
      svg.appendChild(dashed);
    });

    wrapper.appendChild(svg);
    stage.appendChild(wrapper);
    sceneSizer.appendChild(stage);
    viewport.appendChild(sceneSizer);
    shell.appendChild(toolbar);
    shell.appendChild(viewport);
    canvas.appendChild(shell);

    initializeZoomView({
      viewport,
      sceneSizer,
      stage,
      wrapperWidth: width,
      wrapperHeight: height,
      zoomLabel,
      zoomOutBtn,
      zoomInBtn,
      zoomResetBtn,
      zoomFitBtn,
    });
  }

  function initializeZoomView(config) {
    TREE_VIEW_STATE.viewport = config.viewport;
    TREE_VIEW_STATE.sceneSizer = config.sceneSizer;
    TREE_VIEW_STATE.stage = config.stage;
    TREE_VIEW_STATE.wrapperWidth = config.wrapperWidth;
    TREE_VIEW_STATE.wrapperHeight = config.wrapperHeight;
    TREE_VIEW_STATE.zoomLabel = config.zoomLabel;

    config.zoomOutBtn.addEventListener("click", function () {
      applyTreeScale(TREE_VIEW_STATE.scale - TREE_VIEW_STATE.step);
    });

    config.zoomInBtn.addEventListener("click", function () {
      applyTreeScale(TREE_VIEW_STATE.scale + TREE_VIEW_STATE.step);
    });

    config.zoomResetBtn.addEventListener("click", function () {
      applyTreeScale(1);
    });

    config.zoomFitBtn.addEventListener("click", function () {
      applyTreeScale(getFitScale());
    });

    config.viewport.addEventListener(
      "wheel",
      function (event) {
        if (!(event.ctrlKey || event.metaKey)) return;
        event.preventDefault();

        const direction = event.deltaY > 0 ? -1 : 1;
        applyTreeScale(
          TREE_VIEW_STATE.scale + direction * TREE_VIEW_STATE.step,
        );
      },
      { passive: false },
    );

    requestAnimationFrame(function () {
      applyTreeScale(getFitScale());
    });
  }

  function getFitScale() {
    if (!TREE_VIEW_STATE.viewport || !TREE_VIEW_STATE.wrapperWidth) return 1;

    const availableWidth = Math.max(
      320,
      TREE_VIEW_STATE.viewport.clientWidth - 24,
    );
    const fitScale = availableWidth / TREE_VIEW_STATE.wrapperWidth;

    return clampScale(Math.min(1, fitScale));
  }

  function clampScale(value) {
    return Math.max(
      TREE_VIEW_STATE.minScale,
      Math.min(TREE_VIEW_STATE.maxScale, value),
    );
  }

  function applyTreeScale(nextScale) {
    if (
      !TREE_VIEW_STATE.stage ||
      !TREE_VIEW_STATE.sceneSizer ||
      !TREE_VIEW_STATE.wrapperWidth ||
      !TREE_VIEW_STATE.wrapperHeight
    ) {
      return;
    }

    TREE_VIEW_STATE.scale = clampScale(nextScale);

    TREE_VIEW_STATE.stage.style.transform = `scale(${TREE_VIEW_STATE.scale})`;
    TREE_VIEW_STATE.sceneSizer.style.width = `${TREE_VIEW_STATE.wrapperWidth * TREE_VIEW_STATE.scale}px`;
    TREE_VIEW_STATE.sceneSizer.style.height = `${TREE_VIEW_STATE.wrapperHeight * TREE_VIEW_STATE.scale}px`;

    if (TREE_VIEW_STATE.zoomLabel) {
      TREE_VIEW_STATE.zoomLabel.textContent = `${Math.round(TREE_VIEW_STATE.scale * 100)}%`;
    }
  }

  function placeMemberNode(
    wrapper,
    member,
    x,
    y,
    width,
    height,
    detailPanel,
    detailEmpty,
    memberMap,
    relationships,
  ) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "tree-node tree-node-button";
    card.style.left = `${x}px`;
    card.style.top = `${y}px`;

    const name = getDisplayName(member);
    const birth = getBirthYear(member);

    card.innerHTML = `
      <div class="tree-node-name">${escapeHtml(name)}</div>
      <div class="tree-node-meta">Born: ${escapeHtml(birth)}</div>
    `;

    card.addEventListener("click", function () {
      document.querySelectorAll(".tree-node.is-active").forEach((node) => {
        node.classList.remove("is-active");
      });

      card.classList.add("is-active");
      renderDetailPanel(
        member,
        memberMap,
        relationships,
        detailPanel,
        detailEmpty,
      );
    });

    wrapper.appendChild(card);
  }

  function renderDetailPanel(
    member,
    memberMap,
    relationships,
    detailPanel,
    detailEmpty,
  ) {
    if (!detailPanel) return;

    if (detailEmpty) {
      detailEmpty.style.display = "none";
    }

    detailPanel.style.display = "block";

    const spouses = relationships
      .filter(
        (rel) =>
          rel.relationship_type === "spouse" &&
          (rel.source_member_id === member.id ||
            rel.target_member_id === member.id),
      )
      .map((rel) => ({
        person:
          memberMap.get(
            rel.source_member_id === member.id
              ? rel.target_member_id
              : rel.source_member_id,
          ) || null,
        relationship_type: "spouse",
      }))
      .filter((entry) => entry.person);

    const parents = relationships
      .filter(
        (rel) =>
          ANCESTRY_TYPES.has(rel.relationship_type) &&
          rel.target_member_id === member.id,
      )
      .map((rel) => ({
        person: memberMap.get(rel.source_member_id) || null,
        relationship_type: rel.relationship_type,
      }))
      .filter((entry) => entry.person);

    const children = relationships
      .filter(
        (rel) =>
          ANCESTRY_TYPES.has(rel.relationship_type) &&
          rel.source_member_id === member.id,
      )
      .map((rel) => ({
        person: memberMap.get(rel.target_member_id) || null,
        relationship_type: rel.relationship_type,
      }))
      .filter((entry) => entry.person);

    detailPanel.innerHTML = `
      <div class="lineage-profile-card">
        <div class="lineage-profile-header">
          <div class="lineage-profile-badge">Profile</div>
          <h3>${escapeHtml(getDisplayName(member))}</h3>
          <p class="lineage-profile-subtext">Lineage identity record</p>
        </div>

        <div class="lineage-profile-grid">
          <div class="lineage-profile-item">
            <span class="lineage-label">Birth Year</span>
            <span class="lineage-value">${escapeHtml(getBirthYear(member))}</span>
          </div>
          <div class="lineage-profile-item">
            <span class="lineage-label">Generation</span>
            <span class="lineage-value">${escapeHtml(Number.isInteger(member.generation) ? String(member.generation) : "Unknown")}</span>
          </div>
          <div class="lineage-profile-item">
            <span class="lineage-label">Member ID</span>
            <span class="lineage-value lineage-id">${escapeHtml(member.id || "")}</span>
          </div>
          <div class="lineage-profile-item">
            <span class="lineage-label">Family ID</span>
            <span class="lineage-value lineage-id">${escapeHtml(member.family_id || "")}</span>
          </div>
          <div class="lineage-profile-item">
            <span class="lineage-label">Verification</span>
            <span class="lineage-value">${escapeHtml(getVerificationLabel(member))}</span>
          </div>
        </div>

        <div class="lineage-section">
          <h4>Bio</h4>
          <p>${escapeHtml(member.bio || "No bio provided.")}</p>
        </div>

        <div class="lineage-section">
          <h4>Parents</h4>
          ${renderPeopleList(parents, "parents")}
        </div>

        <div class="lineage-section">
          <h4>Spouses</h4>
          ${renderPeopleList(spouses, "spouses")}
        </div>

        <div class="lineage-section">
          <h4>Children</h4>
          ${renderPeopleList(children, "children")}
        </div>
      </div>
    `;
  }

  function renderPeopleList(entries, context) {
    if (!entries || !entries.length) {
      return '<p class="lineage-empty">None recorded.</p>';
    }

    return `
      <ul class="lineage-list">
        ${entries
          .map((entry) => {
            const person = entry.person;
            const relType = formatRelationshipLabel(
              entry.relationship_type,
              context,
            );

            return `
              <li class="lineage-list-item">
                <div>
                  <strong>${escapeHtml(getDisplayName(person))}</strong>
                  <div style="font-size:0.82rem; opacity:0.8;">${escapeHtml(relType)}</div>
                </div>
                <span>${escapeHtml(getBirthYear(person))}</span>
              </li>
            `;
          })
          .join("")}
      </ul>
    `;
  }

  function getItemAnchorX(item, positions, relationships, pairMap) {
    const memberIds = item.members.map((member) => member.id);
    const anchorValues = [];

    memberIds.forEach((memberId) => {
      const parentLinks = relationships.filter(
        (rel) =>
          PRIMARY_ANCESTRY_TYPES.has(rel.relationship_type) &&
          rel.target_member_id === memberId,
      );

      if (!parentLinks.length) return;

      const parentIds = [
        ...new Set(parentLinks.map((rel) => rel.source_member_id)),
      ];
      const parentCenters = [];

      parentIds.forEach((parentId) => {
        const parentPos = positions.get(parentId);
        if (parentPos) {
          parentCenters.push(parentPos.centerX);
          return;
        }

        const pair = pairMap.get(parentId);
        if (pair) {
          const posA = positions.get(pair.a);
          const posB = positions.get(pair.b);
          if (posA && posB) {
            parentCenters.push((posA.centerX + posB.centerX) / 2);
          }
        }
      });

      if (parentCenters.length) {
        anchorValues.push(
          parentCenters.reduce((sum, value) => sum + value, 0) /
            parentCenters.length,
        );
      }
    });

    if (anchorValues.length) {
      return (
        anchorValues.reduce((sum, value) => sum + value, 0) /
        anchorValues.length
      );
    }

    return Number.POSITIVE_INFINITY;
  }

  function getItemSortName(item) {
    return item.members.map((member) => getDisplayName(member)).join(" ");
  }

  function buildMemberRowMap(members, relationships) {
    const memberById = new Map();
    members.forEach((member) => memberById.set(member.id, member));

    const spouseLinks = relationships.filter(
      (rel) => rel.relationship_type === "spouse",
    );
    const spouseGraph = new Map();

    members.forEach((member) => {
      spouseGraph.set(member.id, new Set());
    });

    spouseLinks.forEach((rel) => {
      if (!spouseGraph.has(rel.source_member_id)) {
        spouseGraph.set(rel.source_member_id, new Set());
      }
      if (!spouseGraph.has(rel.target_member_id)) {
        spouseGraph.set(rel.target_member_id, new Set());
      }

      spouseGraph.get(rel.source_member_id).add(rel.target_member_id);
      spouseGraph.get(rel.target_member_id).add(rel.source_member_id);
    });

    const memberRowMap = new Map();
    const visited = new Set();

    members.forEach((member) => {
      if (visited.has(member.id)) return;

      const component = [];
      const queue = [member.id];
      visited.add(member.id);

      while (queue.length) {
        const currentId = queue.shift();
        component.push(currentId);

        const neighbors = spouseGraph.get(currentId) || new Set();
        neighbors.forEach((neighborId) => {
          if (!visited.has(neighborId)) {
            visited.add(neighborId);
            queue.push(neighborId);
          }
        });
      }

      const baseRow = component.reduce((minRow, memberId) => {
        const currentMember = memberById.get(memberId);
        const currentGen = Number.isInteger(currentMember?.generation)
          ? currentMember.generation
          : 0;
        return Math.min(minRow, currentGen);
      }, Infinity);

      component.forEach((memberId) => {
        memberRowMap.set(memberId, baseRow === Infinity ? 0 : baseRow);
      });
    });

    members.forEach((member) => {
      if (!memberRowMap.has(member.id)) {
        memberRowMap.set(
          member.id,
          Number.isInteger(member.generation) ? member.generation : 0,
        );
      }
    });

    return memberRowMap;
  }

  function buildSpousePairs(relationships) {
    const pairs = [];
    const seen = new Set();

    relationships
      .filter((rel) => rel.relationship_type === "spouse")
      .forEach((rel) => {
        const key = buildPairKey(rel.source_member_id, rel.target_member_id);
        if (seen.has(key)) return;

        seen.add(key);
        pairs.push({
          a: rel.source_member_id,
          b: rel.target_member_id,
        });
      });

    return pairs;
  }

  function buildPairKey(a, b) {
    return [a, b].sort().join("::");
  }

  function orderCouple(a, b) {
    const aName = getDisplayName(a);
    const bName = getDisplayName(b);
    return aName.localeCompare(bName) <= 0 ? [a, b] : [b, a];
  }

  function buildPosition(x, y, width, height) {
    return {
      x,
      y,
      centerX: x + width / 2,
      centerY: y + height / 2,
      bottomY: y + height,
      topY: y,
    };
  }

  function findPairedParents(parentIds, spouseSet) {
    for (let i = 0; i < parentIds.length; i += 1) {
      for (let j = i + 1; j < parentIds.length; j += 1) {
        const key = buildPairKey(parentIds[i], parentIds[j]);
        if (spouseSet.has(key)) {
          return [parentIds[i], parentIds[j]];
        }
      }
    }
    return null;
  }

  function makeVerticalLine(svgNS, x, y1, y2, className) {
    const line = document.createElementNS(svgNS, "line");
    line.setAttribute("x1", x);
    line.setAttribute("y1", y1);
    line.setAttribute("x2", x);
    line.setAttribute("y2", y2);
    line.setAttribute("class", className);
    return line;
  }

  function makeCurvedLine(svgNS, x1, y1, x2, y2, className) {
    const path = document.createElementNS(svgNS, "path");
    const midY = y1 + (y2 - y1) / 2;

    const d = [
      `M ${x1} ${y1}`,
      `C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`,
    ].join(" ");

    path.setAttribute("d", d);
    path.setAttribute("class", className);
    return path;
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupTreeViewPage();
  });
})();
