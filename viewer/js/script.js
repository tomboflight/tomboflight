// viewer/js/script.js
// Tomb of Light — Cinematic Viewer
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
  const zoomOutBtn = document.getElementById("zoomOutBtn");
  const zoomInBtn = document.getElementById("zoomInBtn");
  const resetViewerBtn = document.getElementById("resetViewerBtn");
  const backLink = document.getElementById("backLink");

  const stage = document.getElementById("viewerStage");
  const slideshow = document.getElementById("slideshow");

  const gazeShell = document.getElementById("gazeShell");
  const gazeLabel = document.getElementById("gazeLabel");
  const eyeLeft = document.getElementById("eyeLeft");
  const eyeRight = document.getElementById("eyeRight");

  const params = new URLSearchParams(window.location.search);
  const PREVIEW_MODE = params.get("preview") === "1";
  const EMBED_MODE =
    PREVIEW_MODE || params.get("embed") === "1" || window.self !== window.top;

  const NARRATION_DISPLAY_DURATION_MS = 4500;
  const AUTO_ADVANCE_INTERVAL_MS = 5000;
  const DEFAULT_ZOOM_LAYERS = 2;
  const DEFAULT_DYNAMIC_EYE_TARGETS = {
    left: { x: 18, y: 50 },
    right: { x: 82, y: 50 },
  };
  const UNAVAILABLE_MANIFEST = {
    mode: "unavailable",
    navigation_mode: "sequence",
    hero_kicker: "Private Viewer",
    hero_title: "Viewer Access Required",
    hero_body: "No approved viewer manifest is available for this project yet.",
    instructions:
      "Return to your dashboard and open the viewer from your entitled project workspace.",
    path_title: "Viewer Status",
    path_items: ["No approved viewer manifest is available for this project yet."],
    nav_labels: {
      left: "Previous",
      right: "Next",
    },
    initial_state_id: "unavailable",
    controls: {
      allow_lineage_navigation: false,
      allow_zoom: false,
      allow_reset: false,
      allow_narration_auto_advance: false,
      allow_gaze_navigation: false,
      allow_branch_navigation: false,
    },
    states: [
      {
        id: "unavailable",
        image: "",
        title: "Viewer Unavailable",
        status: "Manifest required",
        node: "Private viewer",
        description: "No approved viewer manifest is available for this project yet.",
        narration: "",
        left_state_id: "",
        right_state_id: "",
        eye_targets: DEFAULT_DYNAMIC_EYE_TARGETS,
      },
    ],
  };
  const PREVIEW_MANIFEST = {
    mode: "prototype",
    navigation_mode: "graph",
    hero_kicker: "Genesis Prototype Viewer",
    hero_title: "Moreland Family Lineage Prototype",
    hero_body:
      "Preview a cinematic legacy flow anchored by Malik Moreland and mapped through parent structure and descendant branches.",
    instructions:
      "Use Origins, Future Line, or branch choices to move through the lineage prototype.",
    path_title: "Prototype Path",
    path_items: [
      "Anchor Portrait — Malik Moreland",
      "Parent Structure — Moreland Family Origins",
      "Descendant Branches — Future Legacy Layers",
      "Guided Legacy Build — Package-aware delivery paths",
    ],
    nav_labels: {
      left: "Origins",
      right: "Future Line",
    },
    initial_state_id: "malik_anchor",
    controls: {
      allow_lineage_navigation: true,
      allow_zoom: true,
      allow_reset: true,
      allow_narration_auto_advance: true,
      allow_gaze_navigation: true,
      allow_branch_navigation: true,
      max_zoom_layers: 4,
    },
    family: {
      family_name: "Moreland Family",
      anchor_name: "Malik Moreland",
    },
    states: [
      {
        id: "malik_anchor",
        image: "images/malik.jpg",
        title: "Malik Moreland — Legacy Anchor",
        status: "Genesis node active",
        node: "Malik Moreland",
        description:
          "Anchor portrait and entry node for the Moreland family lineage experience.",
        narration:
          "This prototype begins with Malik Moreland as the anchor portrait for a protected lineage build.",
        left_state_id: "moreland_origins",
        right_state_id: "moreland_descendants",
        eye_targets: {
          left: { x: 20, y: 50 },
          right: { x: 80, y: 50 },
        },
      },
      {
        id: "moreland_origins",
        image: "images/parents.jpg",
        title: "Moreland Family Origins",
        status: "Parent structure",
        node: "Moreland Parent Structure",
        description:
          "Parent nodes and source records are arranged into a protected family origin layer.",
        narration:
          "Origins map the parent structure and evidence trail that supports continuity across generations.",
        left_state_id: "",
        right_state_id: "malik_anchor",
        eye_targets: {
          left: { x: 28, y: 50 },
          right: { x: 72, y: 50 },
        },
      },
      {
        id: "moreland_descendants",
        image: "images/malik_descendants.jpg",
        title: "Future Legacy Layers",
        status: "Descendant branches",
        node: "Moreland Descendant Branches",
        description:
          "Descendant pathways extend forward with package-aware viewer flows and stewardship continuity.",
        narration:
          "Future layers carry memory, identity, and lineage structure forward through descendant branches.",
        left_state_id: "malik_anchor",
        right_state_id: "imani_branch",
        eye_targets: {
          left: { x: 24, y: 50 },
          right: { x: 78, y: 50 },
        },
      },
      {
        id: "imani_branch",
        image: "images/imani_descendants.jpg",
        title: "Family Branch — Imani",
        status: "Branch node",
        node: "Imani Branch",
        description:
          "Branch nodes model how family sub-lines can be explored while preserving protected access boundaries.",
        narration:
          "Branch navigation shows how the lineage engine supports guided exploration without exposing private vault content.",
        left_state_id: "moreland_descendants",
        right_state_id: "selah_branch",
        eye_targets: {
          left: { x: 24, y: 50 },
          right: { x: 77, y: 50 },
        },
      },
      {
        id: "selah_branch",
        image: "images/selah_descendants.jpg",
        title: "Future Legacy Branch — Selah",
        status: "Continuity branch",
        node: "Selah Branch",
        description:
          "Future legacy branches represent long-horizon continuity with controlled narrative and entitlement-aware access.",
        narration:
          "This final prototype branch demonstrates continuity planning for future generations in the Moreland family archive.",
        left_state_id: "imani_branch",
        right_state_id: "",
        eye_targets: {
          left: { x: 25, y: 50 },
          right: { x: 75, y: 50 },
        },
      },
    ],
    branch_options_by_state: {
      malik_anchor: [
        { label: "Open Origins Layer", target_state_id: "moreland_origins" },
        { label: "Open Descendant Layer", target_state_id: "moreland_descendants" },
      ],
      moreland_descendants: [
        { label: "Open Imani Branch", target_state_id: "imani_branch" },
        { label: "Return to Anchor", target_state_id: "malik_anchor" },
      ],
      imani_branch: [
        { label: "Open Selah Branch", target_state_id: "selah_branch" },
        { label: "Back to Descendants", target_state_id: "moreland_descendants" },
      ],
    },
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
  const ZOOM_STEP = 0.12;
  let scaleMax = 1.25;
  const WHEEL_NAVIGATION_THRESHOLD = 48;
  const WHEEL_NAVIGATION_COOLDOWN_MS = 720;

  let pendingWheelDelta = 0;
  let wheelRaf = null;
  let wheelNavigationCooldownUntil = 0;
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

  function clearElement(node) {
    if (!node) return;
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function getCurrentTargets() {
    const config = statesById[state];
    return (
      config?.eyeTargets ||
      (currentManifest?.mode === "dynamic"
        ? DEFAULT_DYNAMIC_EYE_TARGETS
        : DEFAULT_DYNAMIC_EYE_TARGETS)
    );
  }

  function getPortalLabel(side) {
    if (side === "left") {
      return currentManifest?.navLabels?.left || "Origins";
    }
    if (side === "right") {
      return currentManifest?.navLabels?.right || "Future Line";
    }
    return "Iris Gate";
  }

  function updateGazeLabel(side) {
    setText(gazeLabel, getPortalLabel(side));
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
      mode: String(manifest?.mode || "dynamic").trim() || "dynamic",
      navigationMode,
      heroKicker: String(manifest?.hero_kicker || "Private Viewer").trim(),
      heroTitle: String(
        manifest?.hero_title || "Private Family Viewer",
      ).trim(),
      heroBody: String(manifest?.hero_body || "").trim(),
      instructions: String(manifest?.instructions || "").trim(),
      pathTitle: String(manifest?.path_title || "Viewer Path").trim(),
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
      controls:
        manifest && typeof manifest.controls === "object" ? manifest.controls : {},
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

  function isControlEnabled(controlKey, fallback = true) {
    if (!currentManifest) return fallback;
    const controls = currentManifest.controls || {};
    if (Object.prototype.hasOwnProperty.call(controls, controlKey)) {
      return Boolean(controls[controlKey]);
    }
    if (currentManifest.mode === "secure_share") {
      return false;
    }
    return fallback;
  }

  function isSecureShareMode(manifest = currentManifest) {
    return String(manifest?.mode || "").trim() === "secure_share";
  }

  function renderPathList(manifest) {
    if (!pathList) return;

    const items =
      manifest.pathItems.length
        ? manifest.pathItems
        : manifest.states.map(function (item) {
            return `${item.title} — ${item.status || "Viewer Node"}`;
          });

    clearElement(pathList);
    items.forEach(function (item) {
      const row = document.createElement("div");
      row.className = "path-item";
      row.textContent = String(item || "");
      pathList.appendChild(row);
    });
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
      document.title = "Tomb of Light | Private Viewer";
    }
  }

  function applyControlVisibility(manifest) {
    const canLineageNavigate =
      !isSecureShareMode(manifest) &&
      isControlEnabled("allow_lineage_navigation", true);
    const canZoom =
      !isSecureShareMode(manifest) &&
      isControlEnabled("allow_zoom", true);
    const canReset = !isSecureShareMode(manifest);
    const canNarration =
      !isSecureShareMode(manifest) &&
      isControlEnabled("allow_narration_auto_advance", true);

    if (navLeftBtn) navLeftBtn.style.display = canLineageNavigate ? "" : "none";
    if (navRightBtn) navRightBtn.style.display = canLineageNavigate ? "" : "none";
    if (zoomOutBtn) zoomOutBtn.style.display = canZoom ? "" : "none";
    if (zoomInBtn) zoomInBtn.style.display = canZoom ? "" : "none";
    if (resetViewerBtn) resetViewerBtn.style.display = canReset ? "" : "none";
    if (narrationToggleBtn) narrationToggleBtn.style.display = canNarration ? "" : "none";
    if (!canNarration) {
      isPlaying = false;
      stopNarrationAutoAdvance();
      showNarration("");
    }
    if (!isControlEnabled("allow_gaze_navigation", true)) {
      cHeld = false;
      setHoveredPortal("");
      setEyeHintsVisible(false);
    }
  }

  function applyManifest(manifest) {
    currentManifest = normalizeManifest(manifest || UNAVAILABLE_MANIFEST);
    const configuredZoomLayers = Number(currentManifest?.controls?.max_zoom_layers);
    if (Number.isFinite(configuredZoomLayers) && configuredZoomLayers > 0) {
      scaleMax = 1 + configuredZoomLayers * ZOOM_STEP;
    } else {
      scaleMax = 1 + DEFAULT_ZOOM_LAYERS * ZOOM_STEP;
    }
    setZoom(1, false);
    statesById = currentManifest.stateMap;
    stateOrder = currentManifest.stateOrder;
    state = currentManifest.initialStateId || stateOrder[0] || "";

    updateHeaderCopy(currentManifest);
    updateNavLabels();
    renderPathList(currentManifest);
    applyControlVisibility(currentManifest);
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
    if (!isControlEnabled("allow_narration_auto_advance", true)) {
      narrationDisplay.style.opacity = "0";
      return;
    }

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
    if (!isControlEnabled("allow_narration_auto_advance", true)) return;
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
    if (!isControlEnabled("allow_narration_auto_advance", true)) return;
    isPlaying = !isPlaying;
    if (narrationToggleBtn) {
      narrationToggleBtn.textContent = isPlaying
        ? "Narration: ON"
        : "Resume Narration";
    }
    if (isPlaying) {
      showNarration(statesById[state]?.narration || "");
      startNarrationAutoAdvance();
    } else {
      stopNarrationAutoAdvance();
    }
  }

  function pauseNarrationForManualControl() {
    if (EMBED_MODE || !isPlaying) return;
    if (!isControlEnabled("allow_narration_auto_advance", true)) return;
    isPlaying = false;
    if (narrationToggleBtn) {
      narrationToggleBtn.textContent = "Resume Narration";
    }
    stopNarrationAutoAdvance();
  }

  function setZoom(nextScale, smooth = true) {
    if (!viewerImage) return;
    scale = clamp(nextScale, SCALE_MIN, scaleMax);
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

    const targets = getCurrentTargets();

    eyeLeft.style.left = `${targets.left.x}%`;
    eyeLeft.style.top = `${targets.left.y}%`;

    eyeRight.style.left = `${targets.right.x}%`;
    eyeRight.style.top = `${targets.right.y}%`;

    if (gazeShell) {
      const centerX = (Number(targets.left.x) + Number(targets.right.x)) / 2;
      const centerY = (Number(targets.left.y) + Number(targets.right.y)) / 2;
      const span = Math.max(
        10,
        Math.abs(Number(targets.right.x) - Number(targets.left.x)),
      );
      const shellWidth = clamp(span * 3.1, 18, 32);
      const shellHeight = clamp(shellWidth * 0.72, 10, 22);

      gazeShell.style.left = `${centerX}%`;
      gazeShell.style.top = `${centerY}%`;
      gazeShell.style.width = `${shellWidth}%`;
      gazeShell.style.height = `${shellHeight}%`;

      if (gazeLabel) {
        gazeLabel.style.left = `${centerX}%`;
        gazeLabel.style.top = `${centerY - shellHeight * 0.7}%`;
      }
    }
  }

  function setEyeHintsVisible(visible) {
    if (!eyeLeft || !eyeRight) return;
    if (EMBED_MODE) visible = false;

    eyeLeft.classList.toggle("is-visible", visible);
    eyeRight.classList.toggle("is-visible", visible);
    eyeLeft.setAttribute("aria-hidden", visible ? "false" : "true");
    eyeRight.setAttribute("aria-hidden", visible ? "false" : "true");

    if (gazeShell) {
      gazeShell.classList.toggle("is-visible", visible);
      gazeShell.setAttribute("aria-hidden", visible ? "false" : "true");
    }

    if (gazeLabel) {
      gazeLabel.classList.toggle("is-visible", visible);
      gazeLabel.setAttribute("aria-hidden", visible ? "false" : "true");
      updateGazeLabel(visible ? hoveredPortalSide : "");
    }
  }

  function setHoveredPortal(side) {
    hoveredPortalSide = side || "";
    if (eyeLeft) {
      eyeLeft.classList.toggle("is-active", hoveredPortalSide === "left");
    }
    if (eyeRight) {
      eyeRight.classList.toggle("is-active", hoveredPortalSide === "right");
    }
    if (gazeShell) {
      gazeShell.classList.toggle("is-left-armed", hoveredPortalSide === "left");
      gazeShell.classList.toggle("is-right-armed", hoveredPortalSide === "right");
    }
    updateGazeLabel(hoveredPortalSide);
  }

  function onKeyDown(e) {
    if (EMBED_MODE) return;
    if (!isControlEnabled("allow_gaze_navigation", true)) return;
    if (e.key === "c" || e.key === "C") {
      cHeld = true;
      setEyeHintsVisible(true);
    }
  }

  function onKeyUp(e) {
    if (!isControlEnabled("allow_gaze_navigation", true)) return;
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

  function portalCanInteract() {
    return Boolean(gazeShell && gazeShell.classList.contains("is-visible"));
  }

  function resolvePortalSideFromPointer(event) {
    if (!gazeShell) return "";
    const bounds = gazeShell.getBoundingClientRect();
    if (!bounds.width) return "";
    const midpoint = bounds.left + bounds.width / 2;
    return event.clientX <= midpoint ? "left" : "right";
  }

  async function animatePortalTransition(side, nextState) {
    if (!nextState || !viewerImage || gestureNavigationLock) return;

    pauseNarrationForManualControl();
    gestureNavigationLock = true;
    pendingWheelDelta = 0;
    wheelNavigationCooldownUntil = Date.now() + WHEEL_NAVIGATION_COOLDOWN_MS;

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
    if (EMBED_MODE || !portalCanInteract()) return;
    const next = resolveLeftTarget();
    if (next) {
      markInteraction();
      animatePortalTransition("left", next);
    }
  }

  function onEyeRightClick() {
    if (EMBED_MODE || !portalCanInteract()) return;
    const next = resolveRightTarget();
    if (next) {
      markInteraction();
      animatePortalTransition("right", next);
    }
  }

  function selectBranch(targetStateId) {
    if (EMBED_MODE || !targetStateId) return;
    if (!isControlEnabled("allow_branch_navigation", true)) return;
    markInteraction();
    pauseNarrationForManualControl();
    applyState(targetStateId);
  }

  function renderBranchOptions() {
    if (!branchOptions) return;
    if (!isControlEnabled("allow_branch_navigation", true)) {
      clearElement(branchOptions);
      branchOptions.style.display = "none";
      return;
    }

    const branchOptionsForState = Array.isArray(
      currentManifest?.branchOptionsByState?.[state],
    )
      ? currentManifest.branchOptionsByState[state]
      : [];

    clearElement(branchOptions);
    branchOptionsForState.forEach(function (option) {
      const label = String(option?.label || "").trim();
      const targetStateId = String(option?.target_state_id || "").trim();
      if (!label || !targetStateId) return;

      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("data-target-state", targetStateId);
      button.textContent = label;
      branchOptions.appendChild(button);
    });

    branchOptions.style.display = branchOptionsForState.length ? "flex" : "none";
  }

  function onGazeShellPointerEnter(event) {
    if (!isControlEnabled("allow_gaze_navigation", true)) return;
    if (!cHeld || !portalCanInteract()) return;
    setHoveredPortal(resolvePortalSideFromPointer(event));
  }

  function onGazeShellPointerMove(event) {
    if (!isControlEnabled("allow_gaze_navigation", true)) return;
    if (!cHeld || !portalCanInteract()) return;
    setHoveredPortal(resolvePortalSideFromPointer(event));
  }

  function onGazeShellPointerLeave() {
    if (!isControlEnabled("allow_gaze_navigation", true)) return;
    if (!cHeld) return;
    setHoveredPortal("");
  }

  function onGazeShellClick() {
    if (EMBED_MODE || !portalCanInteract()) return;
    if (!isControlEnabled("allow_gaze_navigation", true)) return;
    if (hoveredPortalSide === "left") {
      onEyeLeftClick();
      return;
    }
    if (hoveredPortalSide === "right") {
      onEyeRightClick();
    }
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
    if (!isControlEnabled("allow_lineage_navigation", true)) return;
    markInteraction();
    const next = resolveLeftTarget();
    if (next) animatePortalTransition("left", next);
  }

  function navigateDescendants() {
    if (EMBED_MODE) return;
    if (!isControlEnabled("allow_lineage_navigation", true)) return;
    markInteraction();
    const next = resolveRightTarget();
    if (next) animatePortalTransition("right", next);
  }

  function zoomIn() {
    if (EMBED_MODE) return;
    if (!isControlEnabled("allow_zoom", true)) return;
    markInteraction();
    pauseNarrationForManualControl();
    setZoom(scale + ZOOM_STEP, true);
  }

  function zoomOut() {
    if (EMBED_MODE) return;
    if (!isControlEnabled("allow_zoom", true)) return;
    markInteraction();
    pauseNarrationForManualControl();
    setZoom(scale - ZOOM_STEP, true);
  }

  function resetViewer() {
    if (EMBED_MODE) return;
    if (!isControlEnabled("allow_zoom", true)) return;
    setZoom(1, false);
    applyState(currentManifest?.initialStateId || stateOrder[0] || "");
    if (isPlaying) startNarrationAutoAdvance();
  }

  function onWheel(e) {
    if (EMBED_MODE) return;
    if (!isControlEnabled("allow_gaze_navigation", true)) return;
    e.preventDefault();

    pendingWheelDelta += e.deltaY;

    if (!wheelRaf) {
      wheelRaf = requestAnimationFrame(function () {
        const delta = pendingWheelDelta;
        pendingWheelDelta = 0;
        wheelRaf = null;

        if (Math.abs(delta) < WHEEL_NAVIGATION_THRESHOLD || gestureNavigationLock) {
          return;
        }

        const now = Date.now();
        if (now < wheelNavigationCooldownUntil) {
          return;
        }

        markInteraction();
        pauseNarrationForManualControl();
        wheelNavigationCooldownUntil = now + WHEEL_NAVIGATION_COOLDOWN_MS;

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
    if (!projectId && !familyId) {
      return null;
    }

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
      console.warn("Viewer manifest request failed:", error);
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

    if (gazeShell) {
      gazeShell.addEventListener("pointerenter", onGazeShellPointerEnter);
      gazeShell.addEventListener("pointermove", onGazeShellPointerMove);
      gazeShell.addEventListener("pointerleave", onGazeShellPointerLeave);
      gazeShell.addEventListener("click", onGazeShellClick);
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
    const liveManifest = PREVIEW_MODE ? null : await loadDynamicManifest();
    const selectedManifest = PREVIEW_MODE
      ? PREVIEW_MANIFEST
      : liveManifest || UNAVAILABLE_MANIFEST;
    applyManifest(selectedManifest);
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
