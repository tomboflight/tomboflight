const viewerImage = document.getElementById("viewerImage");
const branchOptions = document.getElementById("branchOptions");
const viewerTitle = document.getElementById("viewerTitle");
const viewerStatus = document.getElementById("viewerStatus");
const currentNode = document.getElementById("currentNode");
const currentDescription = document.getElementById("currentDescription");
const narrationDisplay = document.getElementById("narrationDisplay");
const narrationToggleBtn = document.getElementById("narrationToggleBtn");

const stageShell = document.getElementById("stageShell");
const slideshow = document.getElementById("slideshow");
const eyeLeftEl = document.getElementById("eyeLeft");
const eyeRightEl = document.getElementById("eyeRight");

const states = {
  malik: {
    image: "images/malik.jpg",
    title: "Malik Moreland",
    status: "Anchor Portrait",
    node: "Malik Moreland",
    description: "Starting at the anchor portrait for the Genesis family line.",
    narration:
      "This is Malik Moreland, the anchor portrait of the Genesis family line. From here, the Moreland lineage unfolds across generations.",
    // normalized eye centers (x,y) relative to image box
    eyes: { left: [0.44, 0.40], right: [0.56, 0.40] }
  },
  parents: {
    image: "images/parents.jpg",
    title: "Elias & Clara Moreland",
    status: "Parent Structure",
    node: "Parent Layer",
    description: "Choose a family branch from the shared parent structure.",
    narration:
      "Elias and Clara Moreland represent the foundational parent structure. From this layer, three distinct family branches emerge.",
    eyes: { left: [0.40, 0.38], right: [0.60, 0.38] }
  },
  malik_descendants: {
    image: "images/malik_descendants.jpg",
    title: "Malik Descendants",
    status: "Descendant Layer",
    node: "Malik Descendants",
    description: "Malik's line expands into the next generation.",
    narration:
      "Malik's descendants extend his lineage forward, connecting to the next generation of the Moreland family tree.",
    eyes: { left: [0.44, 0.38], right: [0.56, 0.38] }
  },
  imani: {
    image: "images/imani.jpg",
    title: "Imani Moreland",
    status: "Next Generation Anchor",
    node: "Imani Moreland",
    description: "Imani becomes the next generation anchor portrait.",
    narration:
      "Imani Moreland carries the anchor role for the next generation, continuing the Moreland lineage into new chapters.",
    eyes: { left: [0.45, 0.40], right: [0.57, 0.40] }
  },
  imani_descendants: {
    image: "images/imani_descendants.jpg",
    title: "Imani Descendants",
    status: "Future Legacy Layer",
    node: "Imani Descendants",
    description: "Imani's descendants extend the family line forward.",
    narration:
      "Imani's descendants reach further into the future, extending the Moreland family legacy forward in time.",
    eyes: { left: [0.45, 0.38], right: [0.57, 0.38] }
  },
  julian: {
    image: "images/julian.jpg",
    title: "Julian Moreland",
    status: "Sibling Branch",
    node: "Julian Moreland",
    description: "Julian is a sibling branch with no descendant layer.",
    narration:
      "Julian Moreland is a sibling branch. His path connects back through the shared parent structure without a descendant layer.",
    eyes: { left: [0.44, 0.40], right: [0.56, 0.40] }
  },
  selah: {
    image: "images/selah.jpg",
    title: "Selah Carter",
    status: "Sibling Branch",
    node: "Selah Carter",
    description: "Selah is a sibling branch with her own descendants.",
    narration:
      "Selah Carter branches from the parent structure with her own distinct lineage and family tree.",
    eyes: { left: [0.44, 0.40], right: [0.56, 0.40] }
  },
  selah_descendants: {
    image: "images/selah_descendants.jpg",
    title: "Selah Descendants",
    status: "Descendant Layer",
    node: "Selah Descendants",
    description: "Selah's line expands into her descendant branch.",
    narration:
      "Selah's descendants form her unique branch, expanding the family line outward from the Moreland parent structure.",
    eyes: { left: [0.44, 0.38], right: [0.56, 0.38] }
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

const NARRATION_DISPLAY_DURATION_MS = 4500;
const AUTO_ADVANCE_INTERVAL_MS = 5000;

// gesture thresholds
const ZOOM_IN_TRIGGER = 1.35;
const ZOOM_OUT_TRIGGER = 0.80;

// zoom behavior
const ZOOM_MIN = 0.6;
const ZOOM_MAX = 2.4;

let state = "malik";
let isPlaying = true;
let narrationInterval = null;
let narrationFadeTimeout = null;

// transform state (applied to the IMG)
let scale = 1;
let panX = 0;
let panY = 0;

// pointer tracking for pinch
const pointers = new Map();
let lastPinchDist = null;

// prevent double-trigger spam
let transitionLock = false;

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
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

  narrationFadeTimeout = setTimeout(() => {
    narrationDisplay.style.opacity = "0";
  }, NARRATION_DISPLAY_DURATION_MS);
}

function startNarrationAutoAdvance() {
  if (narrationInterval) clearInterval(narrationInterval);
  narrationInterval = setInterval(() => {
    const currentIndex = stateOrder.indexOf(state);
    const nextIndex = (currentIndex + 1) % stateOrder.length;
    applyState(stateOrder[nextIndex], { soft: true });
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

function setImageTransform() {
  if (!viewerImage) return;
  viewerImage.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
}

function resetTransform() {
  scale = 1;
  panX = 0;
  panY = 0;
  setImageTransform();
}

function positionEyeHints() {
  if (!slideshow || !eyeLeftEl || !eyeRightEl) return;
  const eyes = (states[state] && states[state].eyes) || null;
  if (!eyes) return;

  const rect = slideshow.getBoundingClientRect();
  const [lx, ly] = eyes.left;
  const [rx, ry] = eyes.right;

  eyeLeftEl.style.left = `${lx * rect.width}px`;
  eyeLeftEl.style.top = `${ly * rect.height}px`;
  eyeRightEl.style.left = `${rx * rect.width}px`;
  eyeRightEl.style.top = `${ry * rect.height}px`;
}

function applyState(nextState, opts = { soft: false }) {
  const config = states[nextState];
  if (!config || !viewerImage) return;

  state = nextState;
  transitionLock = true;

  // fade just a touch for cinematic change
  viewerImage.style.opacity = opts.soft ? "0.55" : "0.35";

  setTimeout(() => {
    viewerImage.src = config.image;
    viewerImage.alt = config.node;

    if (viewerTitle) viewerTitle.textContent = config.title;
    if (viewerStatus) viewerStatus.textContent = config.status;
    if (currentNode) currentNode.textContent = config.node;
    if (currentDescription) currentDescription.textContent = config.description;

    resetTransform();
    positionEyeHints();

    viewerImage.style.opacity = "1";
    showNarration(config.narration);

    // parents shows branch selector
    if (branchOptions) {
      branchOptions.style.display = nextState === "parents" ? "flex" : "none";
    }

    setTimeout(() => {
      transitionLock = false;
    }, 200);
  }, 160);
}

/**
 * Decide which eye the user interacted with.
 * Returns "left" or "right".
 */
function nearestEye(clientX, clientY) {
  if (!slideshow) return "right";

  const eyes = (states[state] && states[state].eyes) || null;
  if (!eyes) return "right";

  const rect = slideshow.getBoundingClientRect();
  const left = { x: rect.left + eyes.left[0] * rect.width, y: rect.top + eyes.left[1] * rect.height };
  const right = { x: rect.left + eyes.right[0] * rect.width, y: rect.top + eyes.right[1] * rect.height };

  const dl = (clientX - left.x) ** 2 + (clientY - left.y) ** 2;
  const dr = (clientX - right.x) ** 2 + (clientY - right.y) ** 2;

  return dl <= dr ? "left" : "right";
}

/**
 * Main cinematic rule:
 * left eye  => zoom OUT (to parents)
 * right eye => zoom IN  (to descendants)
 */
function eyePortalAction(whichEye) {
  if (transitionLock) return;

  if (whichEye === "left") {
    zoomOut();
  } else {
    zoomIn();
  }
}

function zoomIn() {
  if (transitionLock) return;

  if (state === "malik") return applyState("malik_descendants");
  if (state === "malik_descendants") return applyState("imani");
  if (state === "imani") return applyState("imani_descendants");
  if (state === "selah") return applyState("selah_descendants");
  if (state === "parents") {
    if (branchOptions) branchOptions.style.display = "flex";
    return;
  }
}

function zoomOut() {
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
  if (transitionLock) return;
  if (branch === "julian") return applyState("julian");
  if (branch === "malik") return applyState("malik");
  if (branch === "selah") return applyState("selah");
}

function resetViewer() {
  resetTransform();
  applyState("malik");
  if (isPlaying) startNarrationAutoAdvance();
}

/* ---------------------------
   Gesture Layer (wheel + pinch + drag)
   --------------------------- */
function handleWheel(e) {
  if (!stageShell || transitionLock) return;
  e.preventDefault();

  const delta = -e.deltaY;
  const zoomFactor = delta > 0 ? 1.07 : 0.93;

  scale = clamp(scale * zoomFactor, ZOOM_MIN, ZOOM_MAX);
  setImageTransform();

  // trigger cinematic transitions
  if (scale >= ZOOM_IN_TRIGGER) {
    resetTransform();
    eyePortalAction("right");
  } else if (scale <= ZOOM_OUT_TRIGGER) {
    resetTransform();
    eyePortalAction("left");
  }
}

function onPointerDown(e) {
  if (!stageShell) return;
  stageShell.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

  // single-pointer tap near eyes (mobile + desktop)
  // if user clicks/taps without moving much, we treat as portal click
  e._tapStart = { x: e.clientX, y: e.clientY, t: Date.now() };
}

function onPointerMove(e) {
  if (!pointers.has(e.pointerId)) return;
  const prev = pointers.get(e.pointerId);
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

  // two-finger pinch
  if (pointers.size === 2) {
    const pts = Array.from(pointers.values());
    const dx = pts[0].x - pts[1].x;
    const dy = pts[0].y - pts[1].y;
    const dist = Math.hypot(dx, dy);

    if (lastPinchDist != null) {
      const ratio = dist / lastPinchDist;
      scale = clamp(scale * ratio, ZOOM_MIN, ZOOM_MAX);
      setImageTransform();

      if (scale >= ZOOM_IN_TRIGGER) {
        lastPinchDist = null;
        resetTransform();
        eyePortalAction("right");
        return;
      }
      if (scale <= ZOOM_OUT_TRIGGER) {
        lastPinchDist = null;
        resetTransform();
        eyePortalAction("left");
        return;
      }
    }

    lastPinchDist = dist;
    return;
  }

  // one-finger drag pan (optional, feels better on mobile)
  if (pointers.size === 1 && prev) {
    const dx = e.clientX - prev.x;
    const dy = e.clientY - prev.y;
    panX += dx;
    panY += dy;

    // clamp pan slightly so it doesn’t fly away
    panX = clamp(panX, -220, 220);
    panY = clamp(panY, -180, 180);

    setImageTransform();
  }
}

function onPointerUp(e) {
  const start = e._tapStart;
  pointers.delete(e.pointerId);

  if (pointers.size < 2) lastPinchDist = null;

  // tap detection (short press + small movement)
  if (start && slideshow) {
    const dt = Date.now() - start.t;
    const dx = Math.abs(e.clientX - start.x);
    const dy = Math.abs(e.clientY - start.y);
    if (dt < 350 && dx < 10 && dy < 10) {
      const which = nearestEye(e.clientX, e.clientY);
      eyePortalAction(which);
    }
  }
}

/* ---------------------------
   Init
   --------------------------- */
if (stageShell) {
  stageShell.addEventListener("wheel", handleWheel, { passive: false });
  stageShell.addEventListener("pointerdown", onPointerDown);
  stageShell.addEventListener("pointermove", onPointerMove);
  stageShell.addEventListener("pointerup", onPointerUp);
  stageShell.addEventListener("pointercancel", onPointerUp);
}

window.addEventListener("resize", () => positionEyeHints());

applyState("malik");
positionEyeHints();
startNarrationAutoAdvance();