(function () {
  "use strict";

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
        "Visual family tree loaded successfully.",
        "success",
      );
    } catch (error) {
      console.error("Tree render error:", error);
      showStatus(statusNode, error.message || "Failed to load tree.", "error");
    }
  }

  function renderStructuredTree(graph, canvas, detailPanel, detailEmpty) {
    const members = graph.members || [];
    const relationships = graph.relationships || [];

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

    const width = 1500;
    const height = topPadding * 2 + sortedRows.length * rowGap + 160;

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
    const placedIds = new Set();
    const rows = [];

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

    rows.forEach((row) => {
      const y = topPadding + row.visualRowIndex * rowGap;

      const label = document.createElement("div");
      label.className = "tree-generation-label";
      label.style.left = "24px";
      label.style.top = `${y + 26}px`;
      label.textContent = `Generation ${row.rowIndex}`;
      wrapper.appendChild(label);

      const enrichedItems = row.items.map((item) => {
        const anchorX = getItemAnchorX(item, positions, relationships, pairMap);
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

    const childLinks = relationships.filter(
      (rel) => rel.relationship_type === "parent_child",
    );
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

    wrapper.appendChild(svg);
    canvas.appendChild(wrapper);
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

    const name =
      member.display_name ||
      `${member.first_name || ""} ${member.last_name || ""}`.trim();
    const birth = member.birth_year ? String(member.birth_year) : "Unknown";

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
      .map((rel) =>
        rel.source_member_id === member.id
          ? rel.target_member_id
          : rel.source_member_id,
      )
      .map((id) => memberMap.get(id))
      .filter(Boolean);

    const parents = relationships
      .filter(
        (rel) =>
          rel.relationship_type === "parent_child" &&
          rel.target_member_id === member.id,
      )
      .map((rel) => memberMap.get(rel.source_member_id))
      .filter(Boolean);

    const children = relationships
      .filter(
        (rel) =>
          rel.relationship_type === "parent_child" &&
          rel.source_member_id === member.id,
      )
      .map((rel) => memberMap.get(rel.target_member_id))
      .filter(Boolean);

    detailPanel.innerHTML = `
      <div class="lineage-profile-card">
        <div class="lineage-profile-header">
          <div class="lineage-profile-badge">Profile</div>
          <h3>${escapeHtml(member.display_name || `${member.first_name || ""} ${member.last_name || ""}`.trim())}</h3>
          <p class="lineage-profile-subtext">Lineage identity record</p>
        </div>

        <div class="lineage-profile-grid">
          <div class="lineage-profile-item">
            <span class="lineage-label">Birth Year</span>
            <span class="lineage-value">${escapeHtml(member.birth_year ? String(member.birth_year) : "Unknown")}</span>
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
        </div>

        <div class="lineage-section">
          <h4>Bio</h4>
          <p>${escapeHtml(member.bio || "No bio provided.")}</p>
        </div>

        <div class="lineage-section">
          <h4>Parents</h4>
          ${renderPeopleList(parents)}
        </div>

        <div class="lineage-section">
          <h4>Spouses</h4>
          ${renderPeopleList(spouses)}
        </div>

        <div class="lineage-section">
          <h4>Children</h4>
          ${renderPeopleList(children)}
        </div>
      </div>
    `;
  }

  function renderPeopleList(people) {
    if (!people || !people.length) {
      return '<p class="lineage-empty">None recorded.</p>';
    }

    return `
      <ul class="lineage-list">
        ${people
          .map(
            (person) => `
          <li class="lineage-list-item">
            <strong>${escapeHtml(person.display_name || `${person.first_name || ""} ${person.last_name || ""}`.trim())}</strong>
            <span>${escapeHtml(person.birth_year ? String(person.birth_year) : "Unknown")}</span>
          </li>
        `,
          )
          .join("")}
      </ul>
    `;
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

  function getItemAnchorX(item, positions, relationships, pairMap) {
    const memberIds = item.members.map((member) => member.id);
    const anchorValues = [];

    memberIds.forEach((memberId) => {
      const parentLinks = relationships.filter(
        (rel) =>
          rel.relationship_type === "parent_child" &&
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
    return item.members
      .map((member) =>
        `${member.first_name || ""} ${member.last_name || ""}`.trim(),
      )
      .join(" ");
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
    const aName = `${a.first_name || ""} ${a.last_name || ""}`.trim();
    const bName = `${b.first_name || ""} ${b.last_name || ""}`.trim();
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

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupTreeViewPage();
  });
})();
