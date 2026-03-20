// viewer/js/script.js

const viewerImage = document.getElementById("viewerImage");
const branchOptions = document.getElementById("branchOptions");
const viewerTitle = document.getElementById("viewerTitle");
const viewerStatus = document.getElementById("viewerStatus");
const currentNode = document.getElementById("currentNode");
const currentDescription = document.getElementById("currentDescription");
const narrationDisplay = document.getElementById("narrationDisplay");
const narrationToggleBtn = document.getElementById("narrationToggleBtn");

const EMBED_MODE =
  new URLSearchParams(window.location.search).get("embed") === "1" ||
  window.self !== window.top;

// --- STATES ---
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

// --- Narration settings ---
const NARRATION_DISPLAY_DURATION_MS = 4500;
const AUTO_ADVANCE_INTERVAL_MS = 5000;

let state = "malik";
let isPlaying = true;
let narrationInterval = null;
let narrationFadeTimeout = null;

// --- Transition + zoom control ---
let transitionLock = false;
let scale = 1; // current zoom scale for full viewer
const SCALE_MIN = 0.65;
const SCALE_MAX = 1.25;

// Smooth wheel handling (prevents trackpad bursts from shaking)
let pendingWheelDelta = 0;
let wheelRaf = null;

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function setImageScale(nextScale) {
  scale = clamp(nextScale, SCALE_MIN, SCALE_MAX);
  if (!viewerImage) return;

  // IMPORTANT: keep origin stable to avoid “jitter”
  viewerImage.style.transformOrigin = "center center";
  viewerImage.style.transform = `translate3d(0,0,0) scale(${scale})`;
}

function resetScale() {
  scale = 1;
  if (!viewerImage) return;
  viewerImage.style.transformOrigin = "center center";
  viewerImage.style.transform = "translate3d(0,0,0) scale(1)";
}

// ---------------------------
// Narration display
// ---------------------------
function showNarration(text) {
  if (!narrationDisplay) return;

  if (narrationFadeTimeout) clearTimeout(narrationFadeTimeout);

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
    if (transitionLock) return;
    const currentIndex = stateOrder.indexOf(state);
    const nextIndex = (currentIndex + 1) % stateOrder.length;
    applyState(stateOrder[nextIndex]);
  }, AUTO_ADVANCE_INTERVAL_MS);
}

function stopNarrationAutoAdvance() {
  if (narrationInterval) clearInterval(narrationInterval);
  narrationInterval = null;

  if (narrationFadeTimeout) clearTimeout(narrationFadeTimeout);
  narrationFadeTimeout = null;

  if (narrationDisplay) narrationDisplay.style.opacity = "0";
}

function toggleNarration() {
  if (EMBED_MODE) return; // watch-only

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
function applyState(nextState) {
  const config = states[nextState];
  if (!config) return;
  if (transitionLock) return;

  transitionLock = true;
  state = nextState;

  // Always reset zoom when switching portraits (prevents “stuck zoom”)
  if (!EMBED_MODE) resetScale();

  if (viewerImage) viewerImage.style.opacity = "0.25";

  setTimeout(() => {
    if (viewerImage) {
      viewerImage.src = config.image;
      viewerImage.alt = config.node;
      viewerImage.style.opacity = "1";

      // In embed preview, ALWAYS force scale=1
      if (EMBED_MODE) {
        viewerImage.style.transform = "translate3d(0,0,0) scale(1)";
        viewerImage.style.transformOrigin = "center center";
      }
    }

    if (viewerTitle) viewerTitle.textContent = config.title;
    if (viewerStatus) viewerStatus.textContent = config.status;
    if (currentNode) currentNode.textContent = config.node;
    if (currentDescription) currentDescription.textContent = config.description;

    showNarration(config.narration);

    if (branchOptions) {
      if (!EMBED_MODE && nextState === "parents") branchOptions.style.display = "flex";
      else branchOptions.style.display = "none";
    }

    setTimeout(() => {
      transitionLock = false;
    }, 140);
  }, 180);
}

// ---------------------------
// Button-based zoom (kept)
// ---------------------------
function zoomIn() {
  if (EMBED_MODE) return;
  if (transitionLock) return;

  if (state === "malik") return applyState("malik_descendants");
  if (state === "malik_descendants") return applyState("imani");
  if (state === "imani") return applyState("imani_descendants");
  if (state === "selah") return applyState("selah_descendants");
  if (state === "parents") {
    if (branchOptions) branchOptions.style.display = "flex";
  }
}

function zoomOut() {
  if (EMBED_MODE) return;
  if (transitionLock) return;

  if (state === "malik") return applyState("parents");
  if (state === "malik_descendants") return applyState("malik");
  if (state === "imani") return applyState("malik_descendants");
  if (state === "imani_descendants") return applyState("imani");
  if (state === "julian") return applyState("parents");
  if (state === "selah") return applyState("parents");
  if (state === "selah_descendants") return applyState("selah");
  if (state === "parents") return applyState("malik");
}

function selectBranch(branch) {
  if (EMBED_MODE) return;
  if (transitionLock) return;

  if (branch === "julian") return applyState("julian");
  if (branch === "malik") return applyState("malik");
  if (branch === "selah") return applyState("selah");
}

function resetViewer() {
  if (EMBED_MODE) return;
  if (transitionLock) return;

  resetScale();
  applyState("malik");
  if (isPlaying) startNarrationAutoAdvance();
}

// Expose for inline onclick handlers
window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.resetViewer = resetViewer;
window.toggleNarration = toggleNarration;
window.selectBranch = selectBranch;

// ---------------------------
// Smooth wheel zoom (FULL VIEWER ONLY)
// ---------------------------
function onWheel(e) {
  if (EMBED_MODE) return;
  if (transitionLock) return;

  // Prevent page scroll inside the stage interaction
  e.preventDefault();

  // Trackpads produce small deltas fast — accumulate & apply in rAF
  pendingWheelDelta += e.deltaY;

  if (!wheelRaf) {
    wheelRaf = requestAnimationFrame(() => {
      // Normalize: scrolling up should zoom in slightly, down zoom out slightly
      const delta = pendingWheelDelta;
      pendingWheelDelta = 0;
      wheelRaf = null;

      // If user is wheel-zooming a lot, allow scaling but not “state change”
      // Holding SHIFT does state navigation (optional)
      if (e.shiftKey) {
        if (delta > 0) zoomOut();
        else zoomIn();
        return;
      }

      const zoomSpeed = 0.0012; // tuned for trackpads
      const next = scale * (1 - delta * zoomSpeed);
      setImageScale(next);
    });
  }
}

// Attach wheel only if full viewer
if (!EMBED_MODE) {
  const stage = document.querySelector(".viewer-stage-shell");
  if (stage) {
    stage.addEventListener("wheel", onWheel, { passive: false });
  }
}

// Boot
applyState("malik");
if (!EMBED_MODE) startNarrationAutoAdvance();