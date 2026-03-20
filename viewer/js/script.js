/* Tomb of Light Viewer — FaceMesh eye targeting + smooth zoom */

const viewerImage = document.getElementById("viewerImage");
const viewerStage = document.getElementById("viewerStage");
const slideshow = document.getElementById("slideshow");
const branchOptions = document.getElementById("branchOptions");
const viewerTitle = document.getElementById("viewerTitle");
const viewerStatus = document.getElementById("viewerStatus");
const currentNode = document.getElementById("currentNode");
const currentDescription = document.getElementById("currentDescription");
const narrationDisplay = document.getElementById("narrationDisplay");
const narrationToggleBtn = document.getElementById("narrationToggleBtn");

const eyeHintLeft = document.getElementById("eyeHintLeft");
const eyeHintRight = document.getElementById("eyeHintRight");

// ---------------------
// State machine
// ---------------------
const states = {
  malik: {
    image: "images/malik.jpg",
    title: "Malik Moreland",
    status: "Anchor Portrait",
    node: "Malik Moreland",
    description: "Starting at the anchor portrait for the Genesis family line.",
    narration: "This is Malik Moreland, the anchor portrait of the Genesis family line. From here, the Moreland lineage unfolds across generations.",
    parents: "parents",
    descendants: "malik_descendants"
  },
  parents: {
    image: "images/parents.jpg",
    title: "Elias & Clara Moreland",
    status: "Parent Structure",
    node: "Parent Layer",
    description: "Choose a family branch from the shared parent structure.",
    narration: "Elias and Clara Moreland represent the foundational parent structure. From this layer, three distinct family branches emerge.",
    parents: "malik",
    descendants: "malik",
    showBranches: true
  },
  malik_descendants: {
    image: "images/malik_descendants.jpg",
    title: "Malik Descendants",
    status: "Descendant Layer",
    node: "Malik Descendants",
    description: "Malik's line expands into the next generation.",
    narration: "Malik's descendants extend his lineage forward, connecting to the next generation of the Moreland family tree.",
    parents: "malik",
    descendants: "imani"
  },
  imani: {
    image: "images/imani.jpg",
    title: "Imani Moreland",
    status: "Next Generation Anchor",
    node: "Imani Moreland",
    description: "Imani becomes the next generation anchor portrait.",
    narration: "Imani Moreland carries the anchor role for the next generation, continuing the Moreland lineage into new chapters.",
    parents: "malik_descendants",
    descendants: "imani_descendants"
  },
  imani_descendants: {
    image: "images/imani_descendants.jpg",
    title: "Imani Descendants",
    status: "Future Legacy Layer",
    node: "Imani Descendants",
    description: "Imani's descendants extend the family line forward.",
    narration: "Imani's descendants reach further into the future, extending the Moreland family legacy forward in time.",
    parents: "imani",
    descendants: "imani"
  },
  julian: {
    image: "images/julian.jpg",
    title: "Julian Moreland",
    status: "Sibling Branch",
    node: "Julian Moreland",
    description: "Julian is a sibling branch with no descendant layer.",
    narration: "Julian Moreland is a sibling branch. His path connects back through the shared parent structure without a descendant layer.",
    parents: "parents",
    descendants: "parents"
  },
  selah: {
    image: "images/selah.jpg",
    title: "Selah Carter",
    status: "Sibling Branch",
    node: "Selah Carter",
    description: "Selah is a sibling branch with her own descendants.",
    narration: "Selah Carter branches from the parent structure with her own distinct lineage and family tree.",
    parents: "parents",
    descendants: "selah_descendants"
  },
  selah_descendants: {
    image: "images/selah_descendants.jpg",
    title: "Selah Descendants",
    status: "Descendant Layer",
    node: "Selah Descendants",
    description: "Selah's line expands into her descendant branch.",
    narration: "Selah's descendants form her unique branch, expanding the family line outward from the Moreland parent structure.",
    parents: "selah",
    descendants: "selah"
  }
};

const stateOrder = ["malik","parents","malik_descendants","imani","imani_descendants","julian","selah","selah_descendants"];

let state = "malik";

// ---------------------
// Narration mode (no fighting user)
// ---------------------
const NARRATION_DISPLAY_DURATION_MS = 4500;
const AUTO_ADVANCE_INTERVAL_MS = 5000;

let isPlaying = true;
let narrationInterval = null;
let narrationFadeTimeout = null;
let userInteractingUntil = 0;

function nowMs(){ return Date.now(); }

function pauseAutoAdvanceFor(ms){
  userInteractingUntil = Math.max(userInteractingUntil, nowMs() + ms);
}

function showNarration(text){
  if (!narrationDisplay) return;
  if (narrationFadeTimeout) clearTimeout(narrationFadeTimeout);

  if (!isPlaying || !text){
    narrationDisplay.style.opacity = "0";
    return;
  }

  narrationDisplay.textContent = text;
  narrationDisplay.style.opacity = "1";

  narrationFadeTimeout = setTimeout(() => {
    narrationDisplay.style.opacity = "0";
  }, NARRATION_DISPLAY_DURATION_MS);
}

function startNarrationAutoAdvance(){
  if (narrationInterval) clearInterval(narrationInterval);

  narrationInterval = setInterval(() => {
    if (!isPlaying) return;
    if (nowMs() < userInteractingUntil) return;

    const currentIndex = stateOrder.indexOf(state);
    const nextIndex = (currentIndex + 1) % stateOrder.length;
    applyState(stateOrder[nextIndex], { cinematic: true });
  }, AUTO_ADVANCE_INTERVAL_MS);
}

function stopNarrationAutoAdvance(){
  if (narrationInterval) clearInterval(narrationInterval);
  narrationInterval = null;
  if (narrationFadeTimeout) clearTimeout(narrationFadeTimeout);
  narrationFadeTimeout = null;
  if (narrationDisplay) narrationDisplay.style.opacity = "0";
}

function toggleNarration(){
  isPlaying = !isPlaying;
  if (narrationToggleBtn){
    narrationToggleBtn.textContent = isPlaying ? "Narration: ON" : "Narration: OFF";
  }
  if (isPlaying){
    showNarration(states[state].narration);
    startNarrationAutoAdvance();
  } else {
    stopNarrationAutoAdvance();
  }
}

// ---------------------
// Smooth zoom engine (continuous)
// ---------------------
let scale = 1;
let targetScale = 1;
let tx = 0;
let ty = 0;
let targetTx = 0;
let targetTy = 0;

const MIN_SCALE = 1;
const MAX_SCALE = 2.2;
const SMOOTHING = 0.18;

function clamp(v, min, max){ return Math.min(max, Math.max(min, v)); }

function applyTransform(){
  if (!viewerImage) return;
  scale += (targetScale - scale) * SMOOTHING;
  tx += (targetTx - tx) * SMOOTHING;
  ty += (targetTy - ty) * SMOOTHING;

  viewerImage.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
  requestAnimationFrame(applyTransform);
}

function resetTransform(){
  scale = 1; targetScale = 1;
  tx = 0; ty = 0;
  targetTx = 0; targetTy = 0;
}

// Convert normalized (0..1) coords to transform offsets so the point becomes centered
function focusOnPoint(nx, ny, zoom){
  if (!viewerStage) return;

  const rect = viewerStage.getBoundingClientRect();
  const cx = rect.width / 2;
  const cy = rect.height / 2;

  // point in stage pixels
  const px = nx * rect.width;
  const py = ny * rect.height;

  const z = clamp(zoom, MIN_SCALE, MAX_SCALE);
  targetScale = z;

  // When scaling around center, translation should bring px/py to center.
  // translate = center - point
  targetTx = (cx - px) * z;
  targetTy = (cy - py) * z;
}

function zoomBy(delta, anchorX, anchorY){
  // anchorX/Y are in stage pixels
  if (!viewerStage) return;
  const rect = viewerStage.getBoundingClientRect();

  const nx = clamp(anchorX / rect.width, 0, 1);
  const ny = clamp(anchorY / rect.height, 0, 1);

  const next = clamp(targetScale + delta, MIN_SCALE, MAX_SCALE);
  focusOnPoint(nx, ny, next);
}

function zoomIn(){
  pauseAutoAdvanceFor(3000);
  const cfg = states[state];
  const next = cfg?.descendants || state;
  applyState(next, { cinematic: true, direction: "in" });
}

function zoomOut(){
  pauseAutoAdvanceFor(3000);
  const cfg = states[state];
  const next = cfg?.parents || state;
  applyState(next, { cinematic: true, direction: "out" });
}

function resetViewer(){
  pauseAutoAdvanceFor(3000);
  resetTransform();
  applyState("malik", { cinematic: false });
  if (isPlaying) startNarrationAutoAdvance();
}

// ---------------------
// Eye detection (FaceMesh)
// ---------------------
// Fallback eye points per image (normalized).
// Fill these once and it becomes perfect forever.
const EYE_FALLBACK = {
  "images/malik.jpg": { left: {x:0.42,y:0.40}, right:{x:0.58,y:0.40} },
  "images/imani.jpg": { left: {x:0.44,y:0.41}, right:{x:0.56,y:0.41} },
  "images/selah.jpg": { left: {x:0.44,y:0.41}, right:{x:0.56,y:0.41} },
  "images/julian.jpg": { left: {x:0.44,y:0.41}, right:{x:0.56,y:0.41} }
};

let lastEye = null; // {left:{x,y}, right:{x,y}} normalized

function setEyeHints(eyes){
  if (!eyes) {
    if (eyeHintLeft) eyeHintLeft.style.opacity = "0";
    if (eyeHintRight) eyeHintRight.style.opacity = "0";
    return;
  }
  if (!viewerStage) return;
  const rect = viewerStage.getBoundingClientRect();

  if (eyeHintLeft && eyes.left){
    eyeHintLeft.style.left = `${eyes.left.x * rect.width}px`;
    eyeHintLeft.style.top = `${eyes.left.y * rect.height}px`;
  }
  if (eyeHintRight && eyes.right){
    eyeHintRight.style.left = `${eyes.right.x * rect.width}px`;
    eyeHintRight.style.top = `${eyes.right.y * rect.height}px`;
  }
}

function dist(a,b){ const dx=a.x-b.x, dy=a.y-b.y; return Math.sqrt(dx*dx+dy*dy); }

async function detectEyesFromImage(imgEl){
  // If FaceMesh isn't available, fall back.
  if (!window.FaceMesh) return null;

  // Use fallback if embed-mode or performance concern? (you can keep it on)
  return new Promise((resolve) => {
    const mesh = new FaceMesh({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
    });

    mesh.setOptions({
      maxNumFaces: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    });

    mesh.onResults((results) => {
      try{
        const faces = results.multiFaceLandmarks || [];
        if (!faces.length) return resolve(null);

        const lm = faces[0];

        // Approx eye centers using a few landmark indices
        // Left eye region (viewer’s left): 33 (outer), 133 (inner)
        // Right eye region: 263 (outer), 362 (inner)
        const leftOuter = lm[33], leftInner = lm[133];
        const rightOuter = lm[263], rightInner = lm[362];

        if (!leftOuter || !leftInner || !rightOuter || !rightInner) return resolve(null);

        const left = { x: (leftOuter.x + leftInner.x)/2, y: (leftOuter.y + leftInner.y)/2 };
        const right = { x: (rightOuter.x + rightInner.x)/2, y: (rightOuter.y + rightInner.y)/2 };

        resolve({ left, right });
      } catch(e){
        resolve(null);
      }
    });

    // Send the still image through FaceMesh
    mesh.send({ image: imgEl });
  });
}

async function resolveEyesForCurrentImage(){
  if (!viewerImage) return null;

  const src = viewerImage.getAttribute("src") || "";
  const fallback = EYE_FALLBACK[src] || null;

  // Always try mesh first; fallback if none.
  const detected = await detectEyesFromImage(viewerImage);
  const eyes = detected || fallback;

  lastEye = eyes;
  setEyeHints(eyes);
  return eyes;
}

// ---------------------
// Click/tap eye logic
// ---------------------
function whichEyeHit(eyes, clientX, clientY){
  if (!viewerStage || !eyes) return null;
  const rect = viewerStage.getBoundingClientRect();
  const p = { x: (clientX - rect.left)/rect.width, y: (clientY - rect.top)/rect.height };

  const dl = dist(p, eyes.left);
  const dr = dist(p, eyes.right);

  // within radius threshold
  const TH = 0.08; // tune
  if (dl < TH && dl < dr) return "left";
  if (dr < TH && dr < dl) return "right";
  return null;
}

function onTapOrClick(e){
  pauseAutoAdvanceFor(4000);
  if (!lastEye) return;

  const eye = whichEyeHit(lastEye, e.clientX, e.clientY);
  if (eye === "left"){
    // left eye => parents
    focusOnPoint(lastEye.left.x, lastEye.left.y, 1.9);
    setTimeout(() => zoomOut(), 260);
  } else if (eye === "right"){
    // right eye => descendants
    focusOnPoint(lastEye.right.x, lastEye.right.y, 1.9);
    setTimeout(() => zoomIn(), 260);
  }
}

// ---------------------
// Input: wheel + pinch
// ---------------------
function setupWheelZoom(){
  if (!viewerStage) return;
  viewerStage.addEventListener("wheel", (e) => {
    e.preventDefault();
    pauseAutoAdvanceFor(2500);

    const delta = e.deltaY > 0 ? -0.08 : 0.08;
    const rect = viewerStage.getBoundingClientRect();
    zoomBy(delta, e.clientX - rect.left, e.clientY - rect.top);
  }, { passive: false });
}

let pinchStartDist = 0;
let pinchStartScale = 1;

function getTouchDist(t1, t2){
  const dx = t1.clientX - t2.clientX;
  const dy = t1.clientY - t2.clientY;
  return Math.sqrt(dx*dx + dy*dy);
}

function setupPinchZoom(){
  if (!viewerStage) return;

  viewerStage.addEventListener("touchstart", (e) => {
    if (e.touches.length === 2){
      pauseAutoAdvanceFor(3000);
      pinchStartDist = getTouchDist(e.touches[0], e.touches[1]);
      pinchStartScale = targetScale;
    }
  }, { passive: true });

  viewerStage.addEventListener("touchmove", (e) => {
    if (e.touches.length === 2){
      e.preventDefault();
      pauseAutoAdvanceFor(3000);

      const distNow = getTouchDist(e.touches[0], e.touches[1]);
      const ratio = distNow / (pinchStartDist || distNow);

      const next = clamp(pinchStartScale * ratio, MIN_SCALE, MAX_SCALE);

      // anchor at midpoint
      const midX = (e.touches[0].clientX + e.touches[1].clientX)/2;
      const midY = (e.touches[0].clientY + e.touches[1].clientY)/2;

      if (viewerStage){
        const rect = viewerStage.getBoundingClientRect();
        const ax = midX - rect.left;
        const ay = midY - rect.top;

        const nx = clamp(ax / rect.width, 0, 1);
        const ny = clamp(ay / rect.height, 0, 1);
        focusOnPoint(nx, ny, next);
      }
    }
  }, { passive: false });
}

// ---------------------
// Apply state
// ---------------------
async function applyState(nextState, opts = {}){
  const config = states[nextState];
  if (!config) return;

  state = nextState;

  if (viewerImage) viewerImage.style.opacity = "0.35";

  // stop fighting transforms during swap
  resetTransform();

  setTimeout(async () => {
    if (viewerImage){
      viewerImage.src = config.image;
      viewerImage.alt = config.node;
      viewerImage.style.opacity = "1";
    }

    if (viewerTitle) viewerTitle.textContent = config.title;
    if (viewerStatus) viewerStatus.textContent = config.status;
    if (currentNode) currentNode.textContent = config.node;
    if (currentDescription) currentDescription.textContent = config.description;

    if (branchOptions){
      branchOptions.style.display = config.showBranches ? "flex" : "none";
    }

    showNarration(config.narration);

    // wait a tick so image is ready, then detect eyes
    setTimeout(() => {
      resolveEyesForCurrentImage();
    }, 250);

  }, 160);
}

function selectBranch(branch){
  pauseAutoAdvanceFor(3000);
  if (branch === "julian") applyState("julian", { cinematic: true });
  if (branch === "malik") applyState("malik", { cinematic: true });
  if (branch === "selah") applyState("selah", { cinematic: true });
}

// ---------------------
// Init
// ---------------------
function init(){
  if (branchOptions) branchOptions.style.display = "none";

  setupWheelZoom();
  setupPinchZoom();

  if (viewerStage){
    viewerStage.addEventListener("click", onTapOrClick);
  }

  applyTransform();            // start render loop
  applyState("malik");         // initial
  startNarrationAutoAdvance(); // narration
}

init();