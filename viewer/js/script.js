/* Tomb of Light Viewer — Gesture Zoom + Eye-Target Routing (Face Mesh)
   Drop-in replacement for viewer/js/script.js

   Adds:
   ✅ Smooth continuous zoom (mouse wheel / trackpad + pinch on mobile)
   ✅ Eye-region targeting via MediaPipe FaceMesh (auto-detect eyes)
   ✅ Left eye => go to PARENTS (up)
   ✅ Right eye => go to DESCENDANTS (down)
   ✅ Always reversible because each node has parent/desc edges
   ✅ Keeps your existing buttons + branch buttons working
   ✅ Stops auto-advance while user interacts, resumes after

   NOTE: You must include FaceMesh scripts in viewer/index.html:
     <script src="https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/face_mesh.js"></script>
     <script src="https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils/drawing_utils.js"></script>
     <script src="js/script.js"></script>
*/

(function () {
  "use strict";

  const viewerImage = document.getElementById("viewerImage");
  const branchOptions = document.getElementById("branchOptions");
  const viewerTitle = document.getElementById("viewerTitle");
  const viewerStatus = document.getElementById("viewerStatus");
  const currentNode = document.getElementById("currentNode");
  const currentDescription = document.getElementById("currentDescription");
  const narrationDisplay = document.getElementById("narrationDisplay");
  const narrationToggleBtn = document.getElementById("narrationToggleBtn");

  if (!viewerImage) {
    console.warn("[TOL] viewerImage not found.");
    return;
  }

  // -----------------------------
  // STATES (your existing content)
  // -----------------------------
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

  // Cinematic loop order (unchanged)
  const stateOrder = [
    "malik",
    "parents",
    "malik_descendants",
    "imani",
    "imani_descendants",
    "julian",
    "selah",
    "selah_descendants"
  ];

  // Graph edges guarantee "get back same"
  // Left eye => parent, Right eye => descendant
  const GRAPH = {
    malik: { parent: "parents", descendant: "malik_descendants" },
    parents: { parent: null, descendant: "malik" }, // default zoom-in from parents returns to Malik

    malik_descendants: { parent: "malik", descendant: "imani" },
    imani: { parent: "malik_descendants", descendant: "imani_descendants" },
    imani_descendants: { parent: "imani", descendant: null },

    julian: { parent: "parents", descendant: null },
    selah: { parent: "parents", descendant: "selah_descendants" },
    selah_descendants: { parent: "selah", descendant: null }
  };

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
    if (narrationInterval) clearInterval(narrationInterval);

    narrationInterval = setInterval(() => {
      const currentIndex = stateOrder.indexOf(state);
      const nextIndex = (currentIndex + 1) % stateOrder.length;
      applyState(stateOrder[nextIndex], { cinematic: true });
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

  window.toggleNarration = function toggleNarration() {
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
  };

  // -----------------------------
  // FaceMesh: detect eye centers
  // -----------------------------
  const EYE_LANDMARKS = {
    left: [33, 133, 159, 145],
    right: [362, 263, 386, 374]
  };

  let faceMesh = null;
  let lastEyeCenters = null; // { left:{x,y}, right:{x,y} } in image pixel coords
  let faceMeshReady = false;

  function canUseFaceMesh() {
    return typeof window.FaceMesh !== "undefined";
  }

  function initFaceMeshIfAvailable() {
    if (!canUseFaceMesh()) {
      console.warn("[TOL] FaceMesh library not found. Eye auto-detect disabled.");
      return;
    }

    faceMesh = new window.FaceMesh({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
    });

    faceMesh.setOptions({
      maxNumFaces: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    });

    faceMesh.onResults((results) => {
      try {
        if (!results || !results.multiFaceLandmarks || !results.multiFaceLandmarks.length) {
          lastEyeCenters = null;
          faceMeshReady = true;
          return;
        }

        const lm = results.multiFaceLandmarks[0];
        const w = viewerImage.naturalWidth || viewerImage.width;
        const h = viewerImage.naturalHeight || viewerImage.height;

        function avgPoint(indices) {
          let sx = 0, sy = 0, c = 0;
          for (const idx of indices) {
            const p = lm[idx];
            if (!p) continue;
            sx += p.x * w;
            sy += p.y * h;
            c += 1;
          }
          if (!c) return null;
          return { x: sx / c, y: sy / c };
        }

        const left = avgPoint(EYE_LANDMARKS.left);
        const right = avgPoint(EYE_LANDMARKS.right);

        lastEyeCenters = left && right ? { left, right } : null;
        faceMeshReady = true;
      } catch (e) {
        console.warn("[TOL] FaceMesh parse failed:", e);
        lastEyeCenters = null;
        faceMeshReady = true;
      }
    });
  }

  async function detectEyesOnCurrentImage() {
    if (!faceMesh) return;

    // Only run face mesh on portrait nodes (parents/desc collages usually won't detect)
    const important = new Set(["malik", "imani", "selah"]);
    if (!important.has(state)) {
      lastEyeCenters = null;
      return;
    }

    try {
      if (viewerImage.decode) await viewerImage.decode();
    } catch (_) {}

    faceMeshReady = false;
    try {
      await faceMesh.send({ image: viewerImage });
    } catch (e) {
      console.warn("[TOL] FaceMesh send failed:", e);
      lastEyeCenters = null;
      faceMeshReady = true;
    }
  }

  function clientToImagePixels(clientX, clientY) {
    const rect = viewerImage.getBoundingClientRect();
    const nx = (clientX - rect.left) / rect.width;
    const ny = (clientY - rect.top) / rect.height;

    const w = viewerImage.naturalWidth || rect.width;
    const h = viewerImage.naturalHeight || rect.height;

    return { x: nx * w, y: ny * h };
  }

  function pickEyeByFocalPoint(clientX, clientY) {
    if (!lastEyeCenters) return null;

    const p = clientToImagePixels(clientX, clientY);
    const dl = Math.hypot(p.x - lastEyeCenters.left.x, p.y - lastEyeCenters.left.y);
    const dr = Math.hypot(p.x - lastEyeCenters.right.x, p.y - lastEyeCenters.right.y);

    if (Math.abs(dl - dr) < 20) return "right";
    return dl < dr ? "left" : "right";
  }

  // -----------------------------
  // Smooth transform (continuous zoom)
  // -----------------------------
  const stage = viewerImage.closest(".viewer-stage-shell") || viewerImage.parentElement;

  let scale = 1;
  let tx = 0;
  let ty = 0;

  const SCALE_MIN = 0.7;
  const SCALE_MAX = 2.2;

  const SNAP_IN = 1.35;
  const SNAP_OUT = 0.78;

  const pointers = new Map();
  let lastPinchDist = null;
  let lastFocal = null;
  let lastEyeChoice = null;

  function clamp(v, a, b) {
    return Math.max(a, Math.min(b, v));
  }

  function applyTransform() {
    viewerImage.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    viewerImage.style.transformOrigin = "center";
  }

  function resetTransform(animate = true) {
    if (animate) viewerImage.style.transition = "transform 420ms ease";
    else viewerImage.style.transition = "";

    scale = 1;
    tx = 0;
    ty = 0;
    applyTransform();

    if (animate) {
      setTimeout(() => {
        viewerImage.style.transition = "";
      }, 450);
    }
  }

  function zoomAt(clientX, clientY, nextScale) {
    const rect = viewerImage.getBoundingClientRect();

    const fx = (clientX - rect.left) / rect.width - 0.5;
    const fy = (clientY - rect.top) / rect.height - 0.5;

    const prevScale = scale;
    scale = clamp(nextScale, SCALE_MIN, SCALE_MAX);

    const ds = scale / prevScale;
    tx = tx * ds - fx * rect.width * (ds - 1);
    ty = ty * ds - fy * rect.height * (ds - 1);

    applyTransform();
  }

  function shouldCommitTransition() {
    return scale > SNAP_IN || scale < SNAP_OUT;
  }

  function resolveTargetFromEyeChoice() {
    const edge = GRAPH[state] || { parent: null, descendant: null };
    if (lastEyeChoice === "left") return edge.parent;
    if (lastEyeChoice === "right") return edge.descendant;
    return null;
  }

  function cinematicHop(nextState) {
    const movingToParent = GRAPH[state] && GRAPH[state].parent === nextState;

    viewerImage.style.transition = "transform 420ms ease, opacity 220ms ease";
    viewerImage.style.opacity = "0.35";

    if (movingToParent) scale = clamp(scale * 0.9, SCALE_MIN, SCALE_MAX);
    else scale = clamp(scale * 1.06, SCALE_MIN, SCALE_MAX);

    applyTransform();

    setTimeout(() => {
      viewerImage.style.transition = "";
      viewerImage.style.opacity = "1";
      resetTransform(false);
      applyState(nextState, { cinematic: true });
    }, 220);
  }

  function commitTransitionIfNeeded() {
    if (!shouldCommitTransition()) return;

    // Special case: parents view (don’t let "left eye" do weird jumps)
    if (state === "parents") {
      const target = lastEyeChoice === "right" || !lastEyeChoice ? GRAPH.parents.descendant : null;
      if (target) cinematicHop(target);
      else resetTransform(true);
      return;
    }

    const target = resolveTargetFromEyeChoice();
    if (!target) {
      resetTransform(true);
      return;
    }

    cinematicHop(target);
  }

  // -----------------------------
  // Pointer events: drag + pinch
  // -----------------------------
  function onPointerDown(e) {
    if (isPlaying) stopNarrationAutoAdvance();

    try { stage.setPointerCapture(e.pointerId); } catch (_) {}

    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

    lastFocal = { x: e.clientX, y: e.clientY };
    lastEyeChoice = pickEyeByFocalPoint(e.clientX, e.clientY);

    if (pointers.size === 2) {
      const pts = Array.from(pointers.values());
      lastPinchDist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      lastFocal = { x: (pts[0].x + pts[1].x) / 2, y: (pts[0].y + pts[1].y) / 2 };
      lastEyeChoice = pickEyeByFocalPoint(lastFocal.x, lastFocal.y);
    }
  }

  function onPointerMove(e) {
    if (!pointers.has(e.pointerId)) return;

    const prev = pointers.get(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

    if (pointers.size === 1) {
      const dx = e.clientX - prev.x;
      const dy = e.clientY - prev.y;
      tx += dx;
      ty += dy;
      applyTransform();
      lastFocal = { x: e.clientX, y: e.clientY };
      lastEyeChoice = pickEyeByFocalPoint(e.clientX, e.clientY);
      return;
    }

    if (pointers.size === 2) {
      const pts = Array.from(pointers.values());
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      if (!lastPinchDist) lastPinchDist = dist;

      const mid = { x: (pts[0].x + pts[1].x) / 2, y: (pts[0].y + pts[1].y) / 2 };
      lastFocal = mid;
      lastEyeChoice = pickEyeByFocalPoint(mid.x, mid.y);

      const delta = dist / lastPinchDist;
      zoomAt(mid.x, mid.y, scale * delta);
      lastPinchDist = dist;

      commitTransitionIfNeeded();
    }
  }

  function onPointerUp(e) {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) lastPinchDist = null;

    if (pointers.size === 0) {
      if (isPlaying) startNarrationAutoAdvance();
      if (scale !== 1 && !shouldCommitTransition()) resetTransform(true);
    }
  }

  // -----------------------------
  // Wheel / trackpad zoom
  // -----------------------------
  function onWheel(e) {
    e.preventDefault();
    if (isPlaying) stopNarrationAutoAdvance();

    const direction = e.deltaY > 0 ? -1 : 1;
    const zoomFactor = 1 + direction * 0.06;

    lastFocal = { x: e.clientX, y: e.clientY };
    lastEyeChoice = pickEyeByFocalPoint(e.clientX, e.clientY);

    zoomAt(e.clientX, e.clientY, scale * zoomFactor);
    commitTransitionIfNeeded();

    if (isPlaying) {
      setTimeout(() => {
        if (isPlaying) startNarrationAutoAdvance();
      }, 650);
    }
  }

  // -----------------------------
  // Buttons (keep compatibility)
  // -----------------------------
  window.zoomIn = function zoomIn() {
    const edge = GRAPH[state] || {};
    const next = edge.descendant;
    if (!next) return;
    lastEyeChoice = "right";
    cinematicHop(next);
  };

  window.zoomOut = function zoomOut() {
    const edge = GRAPH[state] || {};
    const prev = edge.parent;
    if (!prev) return;
    lastEyeChoice = "left";
    cinematicHop(prev);
  };

  window.selectBranch = function selectBranch(branch) {
    if (branch === "julian") cinematicHop("julian");
    if (branch === "malik") cinematicHop("malik");
    if (branch === "selah") cinematicHop("selah");
  };

  window.resetViewer = function resetViewer() {
    resetTransform(true);
    applyState("malik", { cinematic: true });
    if (isPlaying) startNarrationAutoAdvance();
  };

  // -----------------------------
  // Apply state (fade + swap + eye detect)
  // -----------------------------
  async function applyState(nextState, opts = {}) {
    const config = states[nextState];
    if (!config) return;

    state = nextState;

    if (viewerTitle) viewerTitle.textContent = config.title;
    if (viewerStatus) viewerStatus.textContent = config.status;
    if (currentNode) currentNode.textContent = config.node;
    if (currentDescription) currentDescription.textContent = config.description;

    if (branchOptions) {
      branchOptions.style.display = nextState === "parents" ? "flex" : "none";
    }

    viewerImage.style.opacity = "0.35";

    setTimeout(async () => {
      viewerImage.src = config.image;
      viewerImage.alt = config.node;

      viewerImage.onload = async () => {
        viewerImage.style.opacity = "1";
        showNarration(config.narration);

        resetTransform(false);
        await detectEyesOnCurrentImage();
      };

      // If cached:
      try {
        if (viewerImage.complete && viewerImage.naturalWidth) {
          viewerImage.style.opacity = "1";
          showNarration(config.narration);
          resetTransform(false);
          await detectEyesOnCurrentImage();
        }
      } catch (_) {}
    }, opts.cinematic ? 140 : 160);
  }

  // -----------------------------
  // Init listeners
  // -----------------------------
  initFaceMeshIfAvailable();

  if (stage) {
    stage.style.touchAction = "none";
    stage.addEventListener("pointerdown", onPointerDown, { passive: true });
    stage.addEventListener("pointermove", onPointerMove, { passive: true });
    stage.addEventListener("pointerup", onPointerUp, { passive: true });
    stage.addEventListener("pointercancel", onPointerUp, { passive: true });

    stage.addEventListener("wheel", onWheel, { passive: false });
  }

  applyState("malik");
  startNarrationAutoAdvance();

  console.log("[TOL] Gesture zoom + face-eye targeting enabled.");
})();