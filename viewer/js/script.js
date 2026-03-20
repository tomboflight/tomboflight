// viewer/js/script.js
// Tomb of Light — Cinematic Viewer Controls (Option 1: Explicit eye zones)
// ✅ Full viewer: wheel + pinch zoom, hold "C" to reveal eye targets, click Left/Right eye to navigate
// ✅ Embed mode (homepage preview): WATCH-ONLY (no controls, no C-click, no zoom)

(() => {
  const viewerImage = document.getElementById("viewerImage");
  const branchOptions = document.getElementById("branchOptions");
  const viewerTitle = document.getElementById("viewerTitle");
  const viewerStatus = document.getElementById("viewerStatus");
  const currentNode = document.getElementById("currentNode");
  const currentDescription = document.getElementById("currentDescription");
  const narrationDisplay = document.getElementById("narrationDisplay");
  const narrationToggleBtn = document.getElementById("narrationToggleBtn");

  const stage = document.getElementById("viewerStage");
  const slideshow = document.getElementById("slideshow");

  const eyeLeft = document.getElementById("eyeLeft");
  const eyeRight = document.getElementById("eyeRight");

  const EMBED_MODE =
    new URLSearchParams(window.location.search).get("embed") === "1" ||
    window.self !== window.top;

  // ----------------------------
  // STATE GRAPH (your existing flow)
  // ----------------------------
  const states = {
    malik: {
      image: "images/malik.jpg",
      title: "Malik Moreland",
      status: "Anchor Portrait",
      node: "Malik Moreland",
      description: "Starting at the anchor portrait for the Genesis family line.",
      narration:
        "This is Malik Moreland, the anchor portrait of the Genesis family line. From here, the Moreland lineage unfolds across generations."
    },
    parents: {
      image: "images/parents.jpg",
      title: "Elias & Clara Moreland",
      status: "Parent Structure",
      node: "Parent Layer",
      description: "Choose a family branch from the shared parent structure.",
      narration:
        "Elias and Clara Moreland represent the foundational parent structure. From this layer, three distinct family branches emerge."
    },
    malik_descendants: {
      image: "images/malik_descendants.jpg",
      title: "Malik Descendants",
      status: "Descendant Layer",
      node: "Malik Descendants",
      description: "Malik's line expands into the next generation.",
      narration:
        "Malik's descendants extend his lineage forward, connecting to the next generation of the Moreland family tree."
    },
    imani: {
      image: "images/imani.jpg",
      title: "Imani Moreland",
      status: "Next Generation Anchor",
      node: "Imani Moreland",
      description: "Imani becomes the next generation anchor portrait.",
      narration:
        "Imani Moreland carries the anchor role for the next generation, continuing the Moreland lineage into new chapters."
    },
    imani_descendants: {
      image: "images/imani_descendants.jpg",
      title: "Imani Descendants",
      status: "Future Legacy Layer",
      node: "Imani Descendants",
      description: "Imani's descendants extend the family line forward.",
      narration:
        "Imani's descendants reach further into the future, extending the Moreland family legacy forward in time."
    },
    julian: {
      image: "images/julian.jpg",
      title: "Julian Moreland",
      status: "Sibling Branch",
      node: "Julian Moreland",
      description: "Julian is a sibling branch with no descendant layer.",
      narration:
        "Julian Moreland is a sibling branch. His path connects back through the shared parent structure without a descendant layer."
    },
    selah: {
      image: "images/selah.jpg",
      title: "Selah Carter",
      status: "Sibling Branch",
      node: "Selah Carter",
      description: "Selah is a sibling branch with her own descendants.",
      narration:
        "Selah Carter branches from the parent structure with her own distinct lineage and family tree."
    },
    selah_descendants: {
      image: "images/selah_descendants.jpg",
      title: "Selah Descendants",
      status: "Descendant Layer",
      node: "Selah Descendants",
      description: "Selah's line expands into her descendant branch.",
      narration:
        "Selah's descendants form her unique branch, expanding the family line outward from the Moreland parent structure."
    }
  };

  // ----------------------------
  // EYE TARGETS (explicit, per image)
  // Values are % of the IMAGE AREA (not the browser).
  // Tune these later per portrait; these are safe starters.
  // ----------------------------
  const eyeTargets = {
    malik: { left: { x: 44, y: 31 }, right: { x: 56, y: 31 } },
    parents: { left: { x: 40, y: 31 }, right: { x: 60, y: 31 } },
    malik_descendants: { left: { x: 42, y: 33 }, right: { x: 58, y: 33 } },
    imani: { left: { x: 44, y: 30 }, right: { x: 56, y: 30 } },
    imani_descendants: { left: { x: 43, y: 33 }, right: { x: 57, y: 33 } },
    julian: { left: { x: 44, y: 31 }, right: { x: 56, y: 31 } },
    selah: { left: { x: 44, y: 31 }, right: { x: 56, y: 31 } },
    selah_descendants: { left: { x: 43, y: 33 }, right: { x: 57, y: 33 } }
  };

  // ----------------------------
  // NAV RULES FOR EYES
  // Left eye = "ancestry / parents direction"
  // Right eye = "descendants direction"
  // ----------------------------
  function goLeftEye() {
    // ancestry direction
    if (state === "malik") return applyState("parents");
    if (state === "malik_descendants") return applyState("malik");
    if (state === "imani") return applyState("malik_descendants");
    if (state === "imani_descendants") return applyState("imani");
    if (state === "julian") return applyState("parents");
    if (state === "selah") return applyState("parents");
    if (state === "selah_descendants") return applyState("selah");
    if (state === "parents") return applyState("malik"); // collapse back to anchor
  }

  function goRightEye() {
    // descendants direction
    if (state === "malik") return applyState("malik_descendants");
    if (state === "malik_descendants") return applyState("imani");
    if (state === "imani") return applyState("imani_descendants");
    if (state === "selah") return applyState("selah_descendants");
    // parents: don’t use right-eye; branch buttons exist in full viewer
  }

  // ----------------------------
  // Narration
  // ----------------------------
  const NARRATION_DISPLAY_DURATION_MS = 4500;
  const AUTO_ADVANCE_INTERVAL_MS = 5000;

  let state = "malik";
  let isPlaying = true;
  let narrationInterval = null;
  let narrationFadeTimeout = null;

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

    narrationFadeTimeout = setTimeout(() => {
      narrationDisplay.style.opacity = "0";
    }, NARRATION_DISPLAY_DURATION_MS);
  }

  function startNarrationAutoAdvance() {
    if (EMBED_MODE) return; // watch-only
    if (narrationInterval) clearInterval(narrationInterval);

    narrationInterval = setInterval(() => {
      // narration mode can stay as-is or be upgraded later;
      // keep it stable: only auto-advance if user is not currently zooming
      if (isUserInteracting) return;

      // use the existing order you approved
      const order = [
        "malik",
        "parents",
        "malik_descendants",
        "imani",
        "imani_descendants",
        "julian",
        "selah",
        "selah_descendants"
      ];
      const i = order.indexOf(state);
      const next = order[(i + 1) % order.length];
      applyState(next);
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
    if (EMBED_MODE) return; // watch-only preview
    isPlaying = !isPlaying;
    if (narrationToggleBtn) {
      narrationToggleBtn.textContent = isPlaying ? "Narration: ON" : "Narration: OFF";
    }
    if (isPlaying) {
      showNarration(states[state].narration);
      startNarrationAutoAdvance();
    } else {
      stopNarrationAutoAdvance();
    }
  }

  // ----------------------------
  // Transition lock (prevents shaking / double triggers)
  // ----------------------------
  let transitionLock = false;

  function applyState(nextState) {
    if (transitionLock) return;
    const config = states[nextState];
    if (!config) return;

    transitionLock = true;
    state = nextState;

    // reset zoom whenever we change states (prevents weird carry-over)
    setZoom(1, false);

    if (viewerImage) viewerImage.style.opacity = "0.25";

    setTimeout(() => {
      if (viewerImage) {
        viewerImage.src = config.image;
        viewerImage.alt = config.node;
        viewerImage.style.opacity = "1";
      }

      if (viewerTitle) viewerTitle.textContent = config.title;
      if (viewerStatus) viewerStatus.textContent = config.status;
      if (currentNode) currentNode.textContent = config.node;
      if (currentDescription) currentDescription.textContent = config.description;

      showNarration(config.narration);
      placeEyeHints();

      if (branchOptions) {
        if (!EMBED_MODE && nextState === "parents") branchOptions.style.display = "flex";
        else branchOptions.style.display = "none";
      }

      setTimeout(() => {
        transitionLock = false;
      }, 140);
    }, 160);
  }

  // ----------------------------
  // BRANCH SELECT (full viewer only)
  // ----------------------------
  function selectBranch(branch) {
    if (EMBED_MODE) return;
    if (branch === "julian") return applyState("julian");
    if (branch === "malik") return applyState("malik");
    if (branch === "selah") return applyState("selah");
  }
  window.selectBranch = selectBranch;

  // ----------------------------
  // ZOOM (Wheel + Pinch)
  // Applies transform to the IMAGE so it feels continuous.
  // ----------------------------
  let scale = 1;
  const SCALE_MIN = 0.65;
  const SCALE_MAX = 1.25;

  function clamp(v, min, max) {
    return Math.min(max, Math.max(min, v));
  }

  function setZoom(nextScale, smooth = true) {
    if (!viewerImage) return;
    scale = clamp(nextScale, SCALE_MIN, SCALE_MAX);

    // Use translateZ to stabilize GPU and reduce jitter
    viewerImage.style.transition = smooth ? "transform 120ms ease" : "none";
    viewerImage.style.transform = `translateZ(0) scale(${scale})`;
  }

  // Smooth wheel handling (prevents trackpad bursts from shaking)
  let pendingWheelDelta = 0;
  let wheelRaf = null;

  function onWheel(e) {
    if (EMBED_MODE) return;
    e.preventDefault();

    pendingWheelDelta += e.deltaY;

    if (!wheelRaf) {
      wheelRaf = requestAnimationFrame(() => {
        const delta = pendingWheelDelta;
        pendingWheelDelta = 0;
        wheelRaf = null;

        // Smaller factor = smoother trackpads
        const zoomChange = -delta * 0.0007;
        setZoom(scale + zoomChange, true);

        markInteraction();
      });
    }
  }

  // Pinch zoom using Pointer Events (best cross-device)
  let pointers = new Map();
  let startDist = 0;
  let startScale = 1;

  function getDist(a, b) {
    const dx = a.clientX - b.clientX;
    const dy = a.clientY - b.clientY;
    return Math.hypot(dx, dy);
  }

  function onPointerDown(e) {
    if (EMBED_MODE) return;
    if (!stage) return;
    stage.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, e);
    markInteraction();

    if (pointers.size === 2) {
      const [p1, p2] = Array.from(pointers.values());
      startDist = getDist(p1, p2);
      startScale = scale;
    }
  }

  function onPointerMove(e) {
    if (EMBED_MODE) return;
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, e);

    if (pointers.size === 2) {
      const [p1, p2] = Array.from(pointers.values());
      const dist = getDist(p1, p2);
      if (startDist > 0) {
        const ratio = dist / startDist;
        setZoom(startScale * ratio, false);
        markInteraction();
      }
    }
  }

  function onPointerUp(e) {
    if (!pointers.has(e.pointerId)) return;
    pointers.delete(e.pointerId);
    if (pointers.size < 2) startDist = 0;
  }

  // Tracks whether user is actively interacting (used to pause narration auto-advance)
  let isUserInteracting = false;
  let interactionTimeout = null;

  function markInteraction() {
    isUserInteracting = true;
    if (interactionTimeout) clearTimeout(interactionTimeout);
    interactionTimeout = setTimeout(() => {
      isUserInteracting = false;
    }, 900);
  }

  // ----------------------------
  // EYE HINTS + HOLD "C" TO REVEAL
  // ----------------------------
  let cHeld = false;

  function placeEyeHints() {
    if (!eyeLeft || !eyeRight || !slideshow) return;

    const t = eyeTargets[state] || eyeTargets["malik"];
    eyeLeft.style.left = `${t.left.x}%`;
    eyeLeft.style.top = `${t.left.y}%`;

    eyeRight.style.left = `${t.right.x}%`;
    eyeRight.style.top = `${t.right.y}%`;
  }

  function setEyeHintsVisible(visible) {
    if (!eyeLeft || !eyeRight) return;
    if (EMBED_MODE) visible = false;

    eyeLeft.classList.toggle("is-visible", visible);
    eyeRight.classList.toggle("is-visible", visible);
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
    }
  }

  function onEyeLeftClick() {
    if (EMBED_MODE) return;
    if (!cHeld) return; // must hold C
    goLeftEye();
  }

  function onEyeRightClick() {
    if (EMBED_MODE) return;
    if (!cHeld) return; // must hold C
    goRightEye();
  }

  // ----------------------------
  // Existing button controls still work (full viewer only)
  // ----------------------------
  function zoomIn() {
    if (EMBED_MODE) return;
    goRightEye();
  }
  function zoomOut() {
    if (EMBED_MODE) return;
    goLeftEye();
  }
  function resetViewer() {
    if (EMBED_MODE) return;
    setZoom(1, false);
    applyState("malik");
    if (isPlaying) startNarrationAutoAdvance();
  }

  window.zoomIn = zoomIn;
  window.zoomOut = zoomOut;
  window.resetViewer = resetViewer;
  window.toggleNarration = toggleNarration;

  // ----------------------------
  // BOOT
  // ----------------------------
  function boot() {
    // Embed mode: remove any chance of interaction
    if (EMBED_MODE) {
      stopNarrationAutoAdvance();
      if (branchOptions) branchOptions.style.display = "none";
      setEyeHintsVisible(false);
    } else {
      // Full viewer handlers
      if (stage) stage.addEventListener("wheel", onWheel, { passive: false });

      if (stage) {
        stage.addEventListener("pointerdown", onPointerDown);
        stage.addEventListener("pointermove", onPointerMove);
        stage.addEventListener("pointerup", onPointerUp);
        stage.addEventListener("pointercancel", onPointerUp);
        stage.addEventListener("pointerleave", onPointerUp);
      }

      window.addEventListener("keydown", onKeyDown);
      window.addEventListener("keyup", onKeyUp);

      if (eyeLeft) eyeLeft.addEventListener("click", onEyeLeftClick);
      if (eyeRight) eyeRight.addEventListener("click", onEyeRightClick);
    }

    applyState("malik");
    startNarrationAutoAdvance();
  }

  boot();
})();