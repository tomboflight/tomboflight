// viewer/js/script.js
// Tomb of Light — Cinematic Viewer
// Public mode keeps the Moreland demo.
// Signed-in mode loads a customer-specific viewer manifest from the API.

(() => {
  const app = window.TOLApp || null;

  const viewerImage = document.getElementById("viewerImage");
  const viewerEmptyState = document.getElementById("viewerEmptyState");
  const branchOptions = document.getElementById("branchOptions");
  const viewerTitle = document.getElementById("viewerTitle");
  const viewerStatus = document.getElementById("viewerStatus");
  const currentNode = document.getElementById("currentNode");
  const currentDescription = document.getElementById("currentDescription");
  const narrationDisplay = document.getElementById("narrationDisplay");
  const narrationToggleBtn = document.getElementById("narrationToggleBtn");
  const viewerHeaderKicker = document.getElementById("viewerHeaderKicker");
  const viewerHeroTitle = document.getElementById("viewerHeroTitle");
  const viewerHeroBody = document.getElementById("viewerHeroBody");
  const viewerInstructions = document.getElementById("viewerInstructions");
  const pathListTitle = document.getElementById("pathListTitle");
  const pathList = document.getElementById("pathList");
  const navLeftBtn = document.getElementById("navLeftBtn");
  const navRightBtn = document.getElementById("navRightBtn");
  const backLink = document.getElementById("backLink");

  const stage = document.getElementById("viewerStage");
  const slideshow = document.getElementById("slideshow");

  const eyeLeft = document.getElementById("eyeLeft");
  const eyeRight = document.getElementById("eyeRight");

  const params = new URLSearchParams(window.location.search);
  const PREVIEW_MODE = params.get("preview") === "1";
  const EMBED_MODE =
    PREVIEW_MODE || params.get("embed") === "1" || window.self !== window.top;

  const DEMO_MANIFEST = {
    mode: "demo",
    navigation_mode: "branch",
    hero_kicker: "Genesis Prototype",
    hero_title: "Interactive Family Lineage",
    hero_body:
      "Navigate through generations of the Moreland lineage and explore family branches through the Tomb of Light viewer.",
    instructions:
      "Hold C to reveal the lineage portals. Hover a portal and scroll in to enter that line, or scroll out to return. Use the zoom buttons below only when you want a closer look at the portrait. (Full viewer only)",
    path_title: "Lineage Flow",
    path_items: [
      "Malik → Parents",
      "Malik → Descendants",
      "Imani → Descendants",
      "Selah → Descendants",
      "Julian → Parents",
    ],
    nav_labels: {
      left: "Origins",
      right: "Future Line",
    },
    initial_state_id: "malik",
    branch_options_by_state: {
      parents: [
        { label: "Julian", target_state_id: "julian" },
        { label: "Malik", target_state_id: "malik" },
        { label: "Selah", target_state_id: "selah" },
      ],
    },
    states: [
      {
        id: "malik",
        image: "images/malik.jpg",
        title: "Malik Moreland",
        status: "Anchor Portrait",
        node: "Malik Moreland",
        description:
          "Starting at the anchor portrait for the Genesis family line.",
        narration:
          "This is Malik Moreland, the anchor portrait of the Genesis family line. From here, the Moreland lineage unfolds across generations.",
        left_state_id: "parents",
        right_state_id: "malik_descendants",
        eye_targets: { left: { x: 44, y: 31 }, right: { x: 56, y: 31 } },
      },
      {
        id: "parents",
        image: "images/parents.jpg",
        title: "Elias & Clara Moreland",
        status: "Parent Structure",
        node: "Parent Layer",
        description:
          "Choose a family branch from the shared parent structure.",
        narration:
          "Elias and Clara Moreland represent the foundational parent structure. From this layer, three distinct family branches emerge.",
        left_state_id: "malik",
        right_state_id: null,
        eye_targets: { left: { x: 40, y: 31 }, right: { x: 60, y: 31 } },
      },
      {
        id: "malik_descendants",
        image: "images/malik_descendants.jpg",
        title: "Malik Descendants",
        status: "Descendant Layer",
        node: "Malik Descendants",
        description: "Malik's line expands into the next generation.",
        narration:
          "Malik's descendants extend his lineage forward, connecting to the next generation of the Moreland family tree.",
        left_state_id: "malik",
        right_state_id: "imani",
        eye_targets: { left: { x: 42, y: 33 }, right: { x: 58, y: 33 } },
      },
      {
        id: "imani",
        image: "images/imani.jpg",
        title: "Imani Moreland",
        status: "Next Generation Anchor",
        node: "Imani Moreland",
        description: "Imani becomes the next generation anchor portrait.",
        narration:
          "Imani Moreland carries the anchor role for the next generation, continuing the Moreland lineage into new chapters.",
        left_state_id: "malik_descendants",
        right_state_id: "imani_descendants",
        eye_targets: { left: { x: 44, y: 30 }, right: { x: 56, y: 30 } },
      },
      {
        id: "imani_descendants",
        image: "images/imani_descendants.jpg",
        title: "Imani Descendants",
        status: "Future Legacy Layer",
        node: "Imani Descendants",
        description: "Imani's descendants extend the family line forward.",
        narration:
          "Imani's descendants reach further into the future, extending the Moreland family legacy forward in time.",
        left_state_id: "imani",
        right_state_id: null,
        eye_targets: { left: { x: 43, y: 33 }, right: { x: 57, y: 33 } },
      },
      {
        id: "julian",
        image: "images/julian.jpg",
        title: "Julian Moreland",
        status: "Sibling Branch",
        node: "Julian Moreland",
        description: "Julian is a sibling branch with no descendant layer.",
        narration:
          "Julian Moreland is a sibling branch. His path connects back through the shared parent structure without a descendant layer.",
        left_state_id: "parents",
        right_state_id: null,
        eye_targets: { left: { x: 44, y: 31 }, right: { x: 56, y: 31 } },
      },
      {
        id: "selah",
        image: "images/selah.jpg",
        title: "Selah Carter",
        status: "Sibling Branch",
        node: "Selah Carter",
        description: "Selah is a sibling branch with her own descendants.",
        narration:
          "Selah Carter branches from the parent structure with her own distinct lineage and family tree.",
        left_state_id: "parents",
        right_state_id: "selah_descendants",
        eye_targets: { left: { x: 44, y: 31 }, right: { x: 56, y: 31 } },
      },
      {
        id: "selah_descendants",
        image: "images/selah_descendants.jpg",
        title: "Selah Descendants",
        status: "Descendant Layer",
        node: "Selah Descendants",
        description: "Selah's line expands into her descendant branch.",
        narration:
          "Selah's descendants form her unique branch, expanding the family line outward from the Moreland parent structure.",
        left_state_id: "selah",
        right_state_id: null,
        eye_targets: { left: { x: 43, y: 33 }, right: { x: 57, y: 33 } },
      },
    ],
  };

  const NARRATION_DISPLAY_DURATION_MS = 4500;
  const AUTO_ADVANCE_INTERVAL_MS = 5000;
  const DEFAULT_DYNAMIC_EYE_TARGETS = {
    left: { x: 18, y: 50 },
    right: { x: 82, y: 50 },
  };

  let currentManifest = null;
  let statesById = {};
  let stateOrder = [];
  let state = "";
  let isPlaying = true;
  let narrationInterval = null;
  let narrationFadeTimeout = null;
  let transitionLock = false;

  let scale = 1;
  const SCALE_MIN = 0.65;
  const SCALE_MAX = 1.25;
  const ZOOM_STEP = 0.12;

  let pendingWheelDelta = 0;
  let wheelRaf = null;
  let hoveredPortalSide = "";
  let gestureNavigationLock = false;

  let isUserInteracting = false;
  let interactionTimeout = null;
  let cHeld = false;

  function clamp(v, min, max) {
    return Math.min(max, Math.max(min, v));
  }

  function setText(node, value) {
    if (!node) return;
    node.textContent = value || "";
  }

  function getApiBaseUrl() {
    if (app && typeof app.getApiBaseUrl === "function") {
      return app.getApiBaseUrl();
    }
    return "";
  }

  function resolveImageUrl(image) {
    const source = String(image || "").trim();
    if (!source) return "";
    if (/^https?:\/\//i.test(source)) return source;
    if (source.startsWith("/")) {
      const base = getApiBaseUrl();
      return base ? `${base}${source}` : source;
    }
    return source;
  }

  function normalizeManifest(manifest) {
    const states = Array.isArray(manifest?.states) ? manifest.states : [];
    const navigationMode =
      String(manifest?.navigation_mode || "").trim() || "sequence";

    const normalizedStates = states.map(function (rawState, index) {
      const id = String(rawState?.id || `state-${index}`).trim();
      const previousState = states[index - 1];
      const nextState = states[index + 1];

      return {
        id,
        image: resolveImageUrl(rawState?.image),
        title: String(rawState?.title || "Private Workspace").trim(),
        status: String(rawState?.status || "").trim(),
        node: String(rawState?.node || rawState?.title || "Node").trim(),
        description: String(rawState?.description || "").trim(),
        narration: String(
          rawState?.narration || rawState?.description || "",
        ).trim(),
        leftStateId:
          rawState?.left_state_id ||
          (navigationMode === "sequence" && previousState
            ? String(previousState.id || "").trim()
            : ""),
        rightStateId:
          rawState?.right_state_id ||
          (navigationMode === "sequence" && nextState
            ? String(nextState.id || "").trim()
            : ""),
        eyeTargets:
          rawState?.eye_targets ||
          (manifest?.mode === "dynamic"
            ? DEFAULT_DYNAMIC_EYE_TARGETS
            : DEFAULT_DYNAMIC_EYE_TARGETS),
      };
    });

    const normalized = {
      mode: String(manifest?.mode || "demo").trim() || "demo",
      navigationMode,
      heroKicker: String(manifest?.hero_kicker || "Genesis Prototype").trim(),
      heroTitle: String(
        manifest?.hero_title || "Interactive Family Lineage",
      ).trim(),
      heroBody: String(manifest?.hero_body || "").trim(),
      instructions: String(manifest?.instructions || "").trim(),
      pathTitle: String(manifest?.path_title || "Lineage Flow").trim(),
      pathItems: Array.isArray(manifest?.path_items)
        ? manifest.path_items.map(function (item) {
            return String(item || "").trim();
          }).filter(Boolean)
        : [],
      navLabels: {
        left: String(manifest?.nav_labels?.left || "Parents").trim(),
        right: String(manifest?.nav_labels?.right || "Descendants").trim(),
      },
      initialStateId: String(
        manifest?.initial_state_id || normalizedStates[0]?.id || "",
      ).trim(),
      branchOptionsByState:
        manifest && typeof manifest.branch_options_by_state === "object"
          ? manifest.branch_options_by_state
          : {},
      states: normalizedStates,
      project: manifest?.project || null,
      family: manifest?.family || null,
    };

    normalized.stateMap = normalized.states.reduce(function (acc, item) {
      acc[item.id] = item;
      return acc;
    }, {});
    normalized.stateOrder = normalized.states.map(function (item) {
      return item.id;
    });

    return normalized;
  }

  function renderPathList(manifest) {
    if (!pathList) return;

    const items =
      manifest.pathItems.length
        ? manifest.pathItems
        : manifest.states.map(function (item) {
            return `${item.title} — ${item.status || "Viewer Node"}`;
          });

    pathList.innerHTML = items
      .map(function (item) {
        return `<div class="path-item">${item}</div>`;
      })
      .join("");
  }

  function updateNavLabels() {
    setText(navLeftBtn, currentManifest?.navLabels?.left || "Parents");
    setText(
      navRightBtn,
      currentManifest?.navLabels?.right || "Descendants",
    );
  }

  function updateHeaderCopy(manifest) {
    setText(viewerHeaderKicker, manifest.heroKicker);
    setText(viewerHeroTitle, manifest.heroTitle);
    setText(viewerHeroBody, manifest.heroBody);
    setText(viewerInstructions, manifest.instructions);
    setText(pathListTitle, manifest.pathTitle);

    if (backLink) {
      if (manifest.mode === "dynamic") {
        backLink.href = "../dashboard.html";
        backLink.textContent = "← Back to Dashboard";
      } else {
        backLink.href = "../index.html";
        backLink.textContent = "← Back to Tomb of Light";
      }
    }

    if (manifest.mode === "dynamic") {
      document.title = `Tomb of Light | ${manifest.heroTitle}`;
    } else {
      document.title = "Tomb of Light | Genesis Prototype";
    }
  }

  function applyManifest(manifest) {
    currentManifest = normalizeManifest(manifest || DEMO_MANIFEST);
    statesById = currentManifest.stateMap;
    stateOrder = currentManifest.stateOrder;
    state = currentManifest.initialStateId || stateOrder[0] || "";

    updateHeaderCopy(currentManifest);
    updateNavLabels();
    renderPathList(currentManifest);
  }

  function setEmptyState(copy) {
    if (!viewerEmptyState) return;
    if (copy) {
      viewerEmptyState.hidden = false;
      viewerEmptyState.textContent = copy;
    } else {
      viewerEmptyState.hidden = true;
      viewerEmptyState.textContent = "";
    }
  }

  function showNarration(text) {
    if (!narrationDisplay) return;

    if (narrationFadeTimeout) {
      clearTimeout(narrationFadeTimeout);
      narrationFadeTimeout = null;
    }

    if (!isPlaying || !text) {
      narrationDisplay.style.opacity = "0";
      return;
    }

    narrationDisplay.textContent = text;
    narrationDisplay.style.opacity = "1";

    narrationFadeTimeout = setTimeout(function () {
      narrationDisplay.style.opacity = "0";
    }, NARRATION_DISPLAY_DURATION_MS);
  }

  function getNextAutoAdvanceStateId() {
    const currentState = statesById[state];
    if (!currentState) return "";
    if (currentState.rightStateId) return currentState.rightStateId;

    const currentIndex = stateOrder.indexOf(state);
    if (currentIndex === -1 || stateOrder.length < 2) return "";

    return stateOrder[(currentIndex + 1) % stateOrder.length] || "";
  }

  function startNarrationAutoAdvance() {
    if (EMBED_MODE) return;
    if (narrationInterval) clearInterval(narrationInterval);

    narrationInterval = setInterval(function () {
      if (isUserInteracting) return;

      const next = getNextAutoAdvanceStateId();
      if (next && next !== state) {
        applyState(next);
      }
    }, AUTO_ADVANCE_INTERVAL_MS);
  }

  function stopNarrationAutoAdvance() {
    if (narrationInterval) {
      clearInterval(narrationInterval);
      narrationInterval = null;
    }
    if (narrationFadeTimeout) {
      clearTimeout(narrationFadeTimeout);
      narrationFadeTimeout = null;
    }
    if (narrationDisplay) narrationDisplay.style.opacity = "0";
  }

  function toggleNarration() {
    if (EMBED_MODE) return;
    isPlaying = !isPlaying;
    if (narrationToggleBtn) {
      narrationToggleBtn.textContent = isPlaying
        ? "Narration: ON"
        : "Narration: OFF";
    }
    if (isPlaying) {
      showNarration(statesById[state]?.narration || "");
      startNarrationAutoAdvance();
    } else {
      stopNarrationAutoAdvance();
    }
  }

  function setZoom(nextScale, smooth = true) {
    if (!viewerImage) return;
    scale = clamp(nextScale, SCALE_MIN, SCALE_MAX);
    viewerImage.style.transition = smooth ? "transform 120ms ease" : "none";
    viewerImage.style.transform = `translateZ(0) scale(${scale})`;
  }

  function markInteraction() {
    isUserInteracting = true;
    if (interactionTimeout) clearTimeout(interactionTimeout);
    interactionTimeout = setTimeout(function () {
      isUserInteracting = false;
    }, 900);
  }

  function placeEyeHints() {
    if (!eyeLeft || !eyeRight || !slideshow) return;

    const config = statesById[state];
    const targets =
      config?.eyeTargets ||
      (currentManifest?.mode === "dynamic"
        ? DEFAULT_DYNAMIC_EYE_TARGETS
        : DEFAULT_DYNAMIC_EYE_TARGETS);

    eyeLeft.style.left = `${targets.left.x}%`;
    eyeLeft.style.top = `${targets.left.y}%`;

    eyeRight.style.left = `${targets.right.x}%`;
    eyeRight.style.top = `${targets.right.y}%`;
  }

  function setEyeHintsVisible(visible) {
    if (!eyeLeft || !eyeRight) return;
    if (EMBED_MODE) visible = false;

    eyeLeft.classList.toggle("is-visible", visible);
    eyeRight.classList.toggle("is-visible", visible);
    eyeLeft.setAttribute("aria-hidden", visible ? "false" : "true");
    eyeRight.setAttribute("aria-hidden", visible ? "false" : "true");
  }

  function setHoveredPortal(side) {
    hoveredPortalSide = side || "";
    if (eyeLeft) {
      eyeLeft.classList.toggle("is-active", hoveredPortalSide === "left");
    }
    if (eyeRight) {
      eyeRight.classList.toggle("is-active", hoveredPortalSide === "right");
    }
  }

  function onKeyDown(e) {
    if (EMBED_MODE) return;
    if (e.key === "c" || e.key === "C") {
      cHeld = true;
      setEyeHintsVisible(true);
    }
  }

  function onKeyUp(e) {
    if (e.key === "c" || e.key === "C") {
      cHeld = false;
      setEyeHintsVisible(false);
      setHoveredPortal("");
    }
  }

  function resolveLeftTarget() {
    return statesById[state]?.leftStateId || "";
  }

  function resolveRightTarget() {
    return statesById[state]?.rightStateId || "";
  }

  function portalCanInteract(node) {
    return Boolean(node && node.classList.contains("is-visible"));
  }

  async function animatePortalTransition(side, nextState) {
    if (!nextState || !viewerImage || gestureNavigationLock) return;

    gestureNavigationLock = true;

    const config = statesById[state];
    const targets =
      config?.eyeTargets ||
      DEFAULT_DYNAMIC_EYE_TARGETS;
    const target = side === "left" ? targets.left : targets.right;
    const shiftX = clamp((50 - Number(target?.x || 50)) * 0.45, -20, 20);
    const shiftY = clamp((50 - Number(target?.y || 50)) * 0.3, -14, 14);

    viewerImage.style.transition =
      "transform 240ms cubic-bezier(0.22, 1, 0.36, 1), opacity 0.25s ease";
    viewerImage.style.transform = `translate(${shiftX}%, ${shiftY}%) scale(1.24)`;

    await new Promise(function (resolve) {
      window.setTimeout(resolve, 210);
    });

    await applyState(nextState);
    gestureNavigationLock = false;
  }

  function onEyeLeftClick() {
    if (EMBED_MODE || !portalCanInteract(eyeLeft)) return;
    const next = resolveLeftTarget();
    if (next) {
      markInteraction();
      animatePortalTransition("left", next);
    }
  }

  function onEyeRightClick() {
    if (EMBED_MODE || !portalCanInteract(eyeRight)) return;
    const next = resolveRightTarget();
    if (next) {
      markInteraction();
      animatePortalTransition("right", next);
    }
  }

  function selectBranch(targetStateId) {
    if (EMBED_MODE || !targetStateId) return;
    markInteraction();
    applyState(targetStateId);
  }

  function renderBranchOptions() {
    if (!branchOptions) return;

    const branchOptionsForState = Array.isArray(
      currentManifest?.branchOptionsByState?.[state],
    )
      ? currentManifest.branchOptionsByState[state]
      : [];

    branchOptions.innerHTML = branchOptionsForState
      .map(function (option) {
        const label = String(option?.label || "").trim();
        const targetStateId = String(option?.target_state_id || "").trim();
        return label && targetStateId
          ? `<button type="button" data-target-state="${targetStateId}">${label}</button>`
          : "";
      })
      .join("");

    branchOptions.style.display = branchOptionsForState.length ? "flex" : "none";
  }

  async function swapViewerImage(imageUrl, altText) {
    if (!viewerImage) return;

    const resolved = String(imageUrl || "").trim();
    viewerImage.style.opacity = "0.25";

    if (!resolved) {
      viewerImage.classList.add("is-empty");
      viewerImage.removeAttribute("src");
      viewerImage.alt = altText || "";
      viewerImage.style.opacity = "0";
      return;
    }

    await new Promise(function (resolve) {
      const preloaded = new Image();

      preloaded.onload = function () {
        viewerImage.src = resolved;
        viewerImage.alt = altText || "";
        viewerImage.classList.remove("is-empty");
        viewerImage.style.opacity = "1";
        resolve();
      };

      preloaded.onerror = function () {
        viewerImage.src = resolved;
        viewerImage.alt = altText || "";
        viewerImage.classList.remove("is-empty");
        viewerImage.style.opacity = "1";
        resolve();
      };

      preloaded.src = resolved;
    });
  }

  async function applyState(nextState) {
    if (transitionLock) return;
    const config = statesById[nextState];
    if (!config) return;

    transitionLock = true;
    state = nextState;
    setZoom(1, false);

    await swapViewerImage(config.image, config.node);

    setText(viewerTitle, config.title);
    setText(viewerStatus, config.status);
    setText(currentNode, config.node);
    setText(currentDescription, config.description);
    setEmptyState(config.image ? "" : config.description);
    showNarration(config.narration);
    placeEyeHints();
    renderBranchOptions();

    setTimeout(function () {
      transitionLock = false;
    }, 140);
  }

  function navigateParents() {
    if (EMBED_MODE) return;
    markInteraction();
    const next = resolveLeftTarget();
    if (next) animatePortalTransition("left", next);
  }

  function navigateDescendants() {
    if (EMBED_MODE) return;
    markInteraction();
    const next = resolveRightTarget();
    if (next) animatePortalTransition("right", next);
  }

  function zoomIn() {
    if (EMBED_MODE) return;
    markInteraction();
    setZoom(scale + ZOOM_STEP, true);
  }

  function zoomOut() {
    if (EMBED_MODE) return;
    markInteraction();
    setZoom(scale - ZOOM_STEP, true);
  }

  function resetViewer() {
    if (EMBED_MODE) return;
    setZoom(1, false);
    applyState(currentManifest?.initialStateId || stateOrder[0] || "");
    if (isPlaying) startNarrationAutoAdvance();
  }

  function onWheel(e) {
    if (EMBED_MODE) return;
    e.preventDefault();

    pendingWheelDelta += e.deltaY;

    if (!wheelRaf) {
      wheelRaf = requestAnimationFrame(function () {
        const delta = pendingWheelDelta;
        pendingWheelDelta = 0;
        wheelRaf = null;

        if (Math.abs(delta) < 12 || gestureNavigationLock) return;

        markInteraction();

        if (delta < 0) {
          const side =
            hoveredPortalSide ||
            (resolveRightTarget() ? "right" : resolveLeftTarget() ? "left" : "");
          const next =
            side === "left" ? resolveLeftTarget() : resolveRightTarget();
          if (next) {
            animatePortalTransition(side || "right", next);
          }
          return;
        }

        const backTarget = resolveLeftTarget();
        if (backTarget) {
          animatePortalTransition("left", backTarget);
        }
      });
    }
  }

  function onPointerDown(e) {
    if (EMBED_MODE || !stage) return;
    markInteraction();
  }

  function onPointerMove(e) {
    if (EMBED_MODE) return;
    markInteraction();
  }

  function onPointerUp(e) {
    if (EMBED_MODE) return;
  }

  async function loadDynamicManifest() {
    if (EMBED_MODE) return null;
    if (!app || typeof app.apiRequest !== "function") return null;
    if (!app.getToken || !app.getToken()) return null;

    const query = new URLSearchParams();
    const projectId = params.get("project_id");
    const familyId = params.get("family_id");

    if (projectId) query.set("project_id", projectId);
    if (familyId) query.set("family_id", familyId);

    const suffix = query.toString() ? `?${query.toString()}` : "";

    try {
      const manifest = await app.apiRequest(`/viewer/manifest${suffix}`, {
        method: "GET",
      });
      if (manifest && Array.isArray(manifest.states) && manifest.states.length) {
        return manifest;
      }
    } catch (error) {
      console.warn("Viewer manifest fallback to demo:", error);
    }

    return null;
  }

  function bindEvents() {
    if (EMBED_MODE) {
      stopNarrationAutoAdvance();
      if (branchOptions) branchOptions.style.display = "none";
      setEyeHintsVisible(false);
      return;
    }

    if (stage) stage.addEventListener("wheel", onWheel, { passive: false });

    if (stage) {
      stage.addEventListener("pointerdown", onPointerDown);
      stage.addEventListener("pointermove", onPointerMove);
      stage.addEventListener("pointerup", onPointerUp);
    }

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);

    if (eyeLeft) eyeLeft.addEventListener("click", onEyeLeftClick);
    if (eyeRight) eyeRight.addEventListener("click", onEyeRightClick);
    if (eyeLeft) {
      eyeLeft.addEventListener("pointerenter", function () {
        setHoveredPortal("left");
      });
      eyeLeft.addEventListener("pointerleave", function () {
        if (hoveredPortalSide === "left") setHoveredPortal("");
      });
    }
    if (eyeRight) {
      eyeRight.addEventListener("pointerenter", function () {
        setHoveredPortal("right");
      });
      eyeRight.addEventListener("pointerleave", function () {
        if (hoveredPortalSide === "right") setHoveredPortal("");
      });
    }

    if (branchOptions) {
      branchOptions.addEventListener("click", function (event) {
        const button = event.target.closest("[data-target-state]");
        if (!button) return;
        selectBranch(button.getAttribute("data-target-state"));
      });
    }
  }

  async function boot() {
    const liveManifest = await loadDynamicManifest();
    applyManifest(liveManifest || DEMO_MANIFEST);
    bindEvents();
    await applyState(currentManifest.initialStateId || stateOrder[0] || "");
    startNarrationAutoAdvance();
  }

  window.selectBranch = selectBranch;
  window.navigateParents = navigateParents;
  window.navigateDescendants = navigateDescendants;
  window.zoomIn = zoomIn;
  window.zoomOut = zoomOut;
  window.resetViewer = resetViewer;
  window.toggleNarration = toggleNarration;

  boot();
})();
