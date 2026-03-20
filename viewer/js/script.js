/* viewer/js/script.js
   Tomb of Light — Cinematic Viewer Controls (Option 1: Explicit eye zones)
   - Scroll/trackpad wheel zoom
   - Pinch zoom (mobile)
   - Click left/right eye hotspots (optional hold "C" to reveal)
   - Prevents shake by using a single transform pipeline
*/

const viewerImage = document.getElementById("viewerImage");
const viewerTitle = document.getElementById("viewerTitle");
const viewerStatus = document.getElementById("viewerStatus");
const currentNode = document.getElementById("currentNode");
const currentDescription = document.getElementById("currentDescription");
const narrationDisplay = document.getElementById("narrationDisplay");
const narrationToggleBtn = document.getElementById("narrationToggleBtn");

const branchOptions = document.getElementById("branchOptions"); // shown on parents state in full viewer
const stageShell = document.querySelector(".viewer-stage-shell");

// EMBED MODE rules:
// - If you want homepage preview to be interactive, set WATCH_ONLY_EMBED = false
const EMBED_MODE =
  new URLSearchParams(window.location.search).get("embed") === "1" ||
  window.self !== window.top;

const WATCH_ONLY_EMBED = true; // <-- change to false if you want preview interactive

// ---------------------------
// States
// ---------------------------
const states = {
  malik: {
    image: "images/malik.jpg",
    title: "Malik Moreland",
    status: "Anchor Portrait",
    node: "Malik Moreland",
    description: "Starting at the anchor portrait for the Genesis family line.",
    narration:
      "This is Malik Moreland, the anchor portrait of the Genesis family line. From here, the Moreland lineage unfolds across generations.",
    // Eye zones are normalized coordinates relative to the image box (0..1)
    eyes: {
      left: { x: 0.46, y: 0.22 },  // Malik left eye
      right: { x: 0.54, y: 0.22 }  // Malik right eye
    },
    nav: {
      leftEye: "parents",           // left eye -> parents
      rightEye: "malik_descendants" // right eye -> descendants
    }
  },

  parents: {
    image: "images/parents.jpg",
    title: "Elias & Clara Moreland",
    status: "Parent Structure",
    node: "Parent Layer",
    description: "Choose a family branch from the shared parent structure.",
    narration:
      "Elias and Clara Moreland represent the foundational parent structure. From this layer, three distinct family branches emerge.",
    // Parents image is special: you can use face regions for sibling selection later.
    // For now, eye clicks return to Malik by default.
    eyes: {
      left: { x: 0.46, y: 0.22 },
      right: { x: 0.54, y: 0.22 }
    },
    nav: {
      leftEye: "malik",
      rightEye: "malik"
    }
  },

  malik_descendants: {
    image: "images/malik_descendants.jpg",
    title: "Malik Descendants",
    status: "Descendant Layer",
    node: "Malik Descendants",
    description: "Malik's line expands into the next generation.",
    narration:
      "Malik's descendants extend his lineage forward, connecting to the next generation of the Moreland family tree.",
    eyes: {
      left: { x: 0.42, y: 0.26 },
      right: { x: 0.58, y: 0.26 }
    },
    nav: {
      leftEye: "malik",
      rightEye: "imani"
    }
  },

  imani: {
    image: "images/imani.jpg",
    title: "Imani Moreland",
    status: "Next Generation Anchor",
    node: "Imani Moreland",
    description: "Imani becomes the next generation anchor portrait.",
    narration:
      "Imani Moreland carries the anchor role for the next generation, continuing the Moreland lineage into new chapters.",
    eyes: {
      left: { x: 0.46, y: 0.22 },
      right: { x: 0.54, y: 0.22 }
    },
    nav: {
      leftEye: "malik_descendants",
      rightEye: "imani_descendants"
    }
  },

  imani_descendants: {
    image: "images/imani_descendants.jpg",
    title: "Imani Descendants",
    status: "Future Legacy Layer",
    node: "Imani Descendants",
    description: "Imani's descendants extend the family line forward.",
    narration:
      "Imani's descendants reach further into the future, extending the Moreland family legacy forward in time.",
    eyes: {
      left: { x: 0.46, y: 0.22 },
      right: { x: 0.54, y: 0.22 }
    },
    nav: {
      leftEye: "imani",
      rightEye: "imani"
    }
  },

  julian: {
    image: "images/julian.jpg",
    title: "Julian Moreland",
    status: "Sibling Branch",
    node: "Julian Moreland",
    description: "Julian is a sibling branch with no descendant layer.",
    narration:
      "Julian Moreland is a sibling branch. His path connects back through the shared parent structure without a descendant layer.",
    eyes: {
      left: { x: 0.46, y: 0.22 },
      right: { x: 0.54, y: 0.22 }
    },
    nav: {
      leftEye: "parents",
      rightEye: "parents"
    }
  },

  selah: {
    image: "images/selah.jpg",
    title: "Selah Carter",
    status: "Sibling Branch",
    node: "Selah Carter",
    description: "Selah is a sibling branch with her own descendants.",
    narration:
      "Selah Carter branches from the parent structure with her own distinct lineage and family tree.",
    eyes: {
      left: { x: 0.46, y: 0.22 },
      right: { x: 0.54, y: 0.22 }
    },
    nav: {
      leftEye: "parents",
      rightEye: "selah_descendants"
    }
  },

  selah_descendants: {
    image: "images/selah_descendants.jpg",
    title: "Selah Descendants",
    status: "Descendant Layer",
    node: "Selah Descendants",
    description: "Selah's line expands into her descendant branch.",
    narration:
      "Selah's descendants form her unique branch, expanding the family line outward from the Moreland parent structure.",
    eyes: {
      left: { x: 0.46, y: 0.22 },
      right: { x: 0.54, y: 0.22 }
    },
    nav: {
      leftEye: "selah",
      rightEye: "selah"
    }
  }
};

// The narration autoplay order (unchanged)
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

// ---------------------------
// Cinematic Transform Engine (NO SHAKE)
// ---------------------------
let state = "malik";
let isPlaying = true;

const NARRATION_DISPLAY_DURATION_MS = 4500;
const AUTO_ADVANCE_INTERVAL_MS = 5000;

let narrationInterval = null;
let narrationFadeTimeout = null;
let transitionLock = false;

// Single transform pipeline
let zoom = 1; // 1..3
let tx = 0;   // px
let ty = 0;   // px

const ZOOM_MIN = 1;
const ZOOM_MAX = 3;
const ZOOM_STEP = 0.18;
const ZOOM_THRESHOLD_IN = 1.35;
const ZOOM_THRESHOLD_OUT = 0.95;

// Eye overlay (optional)
let showEyes = false;

// Helpers
function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function getImageRect() {
  if (!viewerImage) return null;
  return viewerImage.getBoundingClientRect();
}

function applyTransform() {
  if (!viewerImage) return;
  viewerImage.style.transform = `translate3d(${tx}px, ${ty}px, 0) scale(${zoom})`;
}

function resetTransform() {
  zoom = 1;
  tx = 0;
  ty = 0;
  applyTransform();
}

function focusOnNormalizedPoint(nx, ny, targetZoom = 2.2) {
  const rect = getImageRect();
  if (!rect) return;

  zoom = clamp(targetZoom, ZOOM_MIN, ZOOM_MAX);

  // Convert normalized point inside the image rect into pixel coords
  const px = rect.left + rect.width * nx;
  const py = rect.top + rect.height * ny;

  // Center that point in the stage
  const stageRect = stageShell ? stageShell.getBoundingClientRect() : rect;
  const cx = stageRect.left + stageRect.width / 2;
  const cy = stageRect.top + stageRect.height / 2;

  // Translate image so point moves toward center
  // Since we scale the image, translate amount should be scaled too
  tx += (cx - px);
  ty += (cy - py);

  // damp translation to avoid extreme jump
  tx = clamp(tx, -rect.width * 0.4, rect.width * 0.4);
  ty = clamp(ty, -rect.height * 0.4, rect.height * 0.4);

  applyTransform();
}

// ---------------------------
// Narration
// ---------------------------
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
    applyState(stateOrder[nextIndex], { cinematic: false }); // narration is "watch mode"
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
  if (EMBED_MODE && WATCH_ONLY_EMBED) return;

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

// ---------------------------
// State transitions
// ---------------------------
function applyState(nextState, opts = { cinematic: true }) {
  const config = states[nextState];
  if (!config) return;
  if (transitionLock) return;

  transitionLock = true;
  state = nextState;

  // Fade out image
  if (viewerImage) viewerImage.style.opacity = "0.15";

  setTimeout(() => {
    if (viewerImage) {
      viewerImage.src = config.image;
      viewerImage.alt = config.node;
      viewerImage.style.opacity = "1";
      resetTransform();
    }

    if (viewerTitle) viewerTitle.textContent = config.title;
    if (viewerStatus) viewerStatus.textContent = config.status;
    if (currentNode) currentNode.textContent = config.node;
    if (currentDescription) currentDescription.textContent = config.description;

    showNarration(config.narration);

    // Parent branch buttons only in full viewer
    if (branchOptions) {
      if (!EMBED_MODE || !WATCH_ONLY_EMBED) {
        branchOptions.style.display = nextState === "parents" ? "flex" : "none";
      } else {
        branchOptions.style.display = "none";
      }
    }

    // Unlock
    setTimeout(() => {
      transitionLock = false;
    }, 180);
  }, 180);
}

// ---------------------------
// Eye click navigation (Option 1)
// ---------------------------
function getEyeHitSide(clientX, clientY) {
  const rect = getImageRect();
  if (!rect) return null;

  const xNorm = (clientX - rect.left) / rect.width;
  const yNorm = (clientY - rect.top) / rect.height;

  // Simple split by centerline for "left vs right" eye choice
  if (xNorm < 0 || xNorm > 1 || yNorm < 0 || yNorm > 1) return null;
  return xNorm < 0.5 ? "left" : "right";
}

function handleEyeClick(clientX, clientY) {
  const cfg = states[state];
  if (!cfg || !cfg.nav) return;

  const side = getEyeHitSide(clientX, clientY);
  if (!side) return;

  // Cinematic focus first
  const eye = cfg.eyes?.[side];
  if (eye) focusOnNormalizedPoint(eye.x, eye.y, 2.2);

  // Then transition to next state
  const next = side === "left" ? cfg.nav.leftEye : cfg.nav.rightEye;
  if (next) {
    setTimeout(() => applyState(next, { cinematic: true }), 260);
  }
}

// ---------------------------
// Scroll + pinch zoom (cross-device)
// ---------------------------
function zoomBy(delta, anchorX, anchorY) {
  const rect = getImageRect();
  if (!rect) return;

  // Normalize anchor
  const nx = (anchorX - rect.left) / rect.width;
  const ny = (anchorY - rect.top) / rect.height;

  const prevZoom = zoom;
  zoom = clamp(zoom + delta, ZOOM_MIN, ZOOM_MAX);

  // Adjust translation to keep anchor stable
  // Basic approach: scale translation relative to zoom change
  const scale = zoom / prevZoom;
  tx *= scale;
  ty *= scale;

  applyTransform();

  // If user zooms far enough, trigger state transitions (only full viewer or interactive embed)
  if (EMBED_MODE && WATCH_ONLY_EMBED) return;

  if (zoom >= ZOOM_THRESHOLD_IN) {
    // treat as zoom-in intent => go right-eye path (descendants)
    const cfg = states[state];
    const next = cfg?.nav?.rightEye;
    if (next) {
      resetTransform();
      applyState(next, { cinematic: true });
    }
  } else if (zoom <= ZOOM_THRESHOLD_OUT) {
    // treat as zoom-out intent => go left-eye path (parents)
    const cfg = states[state];
    const next = cfg?.nav?.leftEye;
    if (next) {
      resetTransform();
      applyState(next, { cinematic: true });
    }
  }
}

let pinchStartDist = null;

function distance(t1, t2) {
  const dx = t1.clientX - t2.clientX;
  const dy = t1.clientY - t2.clientY;
  return Math.sqrt(dx * dx + dy * dy);
}

// ---------------------------
// Event wiring
// ---------------------------
function bindEvents() {
  if (!stageShell) return;

  // Wheel / trackpad
  stageShell.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      if (transitionLock) return;

      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      zoomBy(delta, e.clientX, e.clientY);
    },
    { passive: false }
  );

  // Click eye navigation
  stageShell.addEventListener("click", (e) => {
    if (transitionLock) return;
    if (EMBED_MODE && WATCH_ONLY_EMBED) return;
    // If holding C, we allow eye click; if not holding C, still allow.
    handleEyeClick(e.clientX, e.clientY);
  });

  // Touch pinch
  stageShell.addEventListener(
    "touchstart",
    (e) => {
      if (transitionLock) return;
      if (e.touches.length === 2) {
        pinchStartDist = distance(e.touches[0], e.touches[1]);
      }
    },
    { passive: true }
  );

  stageShell.addEventListener(
    "touchmove",
    (e) => {
      if (transitionLock) return;
      if (e.touches.length === 2 && pinchStartDist) {
        e.preventDefault();
        const d = distance(e.touches[0], e.touches[1]);
        const diff = d - pinchStartDist;
        pinchStartDist = d;

        const centerX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        const centerY = (e.touches[0].clientY + e.touches[1].clientY) / 2;

        const delta = diff > 0 ? ZOOM_STEP * 0.6 : -ZOOM_STEP * 0.6;
        zoomBy(delta, centerX, centerY);
      }
    },
    { passive: false }
  );

  stageShell.addEventListener(
    "touchend",
    () => {
      pinchStartDist = null;
    },
    { passive: true }
  );

  // Hold C to show eye hints (optional – uses CSS .show-eyes)
  window.addEventListener("keydown", (e) => {
    if (e.key.toLowerCase() === "c") {
      showEyes = true;
      document.body.classList.add("show-eyes");
    }
  });

  window.addEventListener("keyup", (e) => {
    if (e.key.toLowerCase() === "c") {
      showEyes = false;
      document.body.classList.remove("show-eyes");
    }
  });
}

// Branch buttons (only used on parents)
window.selectBranch = function selectBranch(branch) {
  if (EMBED_MODE && WATCH_ONLY_EMBED) return;
  if (transitionLock) return;

  if (branch === "julian") applyState("julian");
  if (branch === "malik") applyState("malik");
  if (branch === "selah") applyState("selah");
};

window.toggleNarration = toggleNarration;

window.resetViewer = function resetViewer() {
  if (EMBED_MODE && WATCH_ONLY_EMBED) return;
  resetTransform();
  applyState("malik");
  if (isPlaying) startNarrationAutoAdvance();
};

// Boot
applyState("malik");
bindEvents();
startNarrationAutoAdvance();