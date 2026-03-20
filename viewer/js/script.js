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

const NARRATION_DISPLAY_DURATION_MS = 4500;
const AUTO_ADVANCE_INTERVAL_MS = 5000;

let state = "malik";
let isPlaying = true;
let narrationInterval = null;
let narrationFadeTimeout = null;
let transitionLock = false;

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
    applyState(stateOrder[nextIndex]);
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
  if (EMBED_MODE) return; // watch-only on homepage preview

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

function applyState(nextState) {
  const config = states[nextState];
  if (!config) return;
  if (transitionLock) return;

  transitionLock = true;
  state = nextState;

  // Simple crossfade (no zoom transforms in embed-mode)
  if (viewerImage) viewerImage.style.opacity = "0.25";

  setTimeout(() => {
    if (viewerImage) {
      viewerImage.src = config.image;
      viewerImage.alt = config.node;
      viewerImage.classList.remove("zoom-in", "zoom-out");
      viewerImage.style.opacity = "1";
    }

    if (viewerTitle) viewerTitle.textContent = config.title;
    if (viewerStatus) viewerStatus.textContent = config.status;
    if (currentNode) currentNode.textContent = config.node;
    if (currentDescription) currentDescription.textContent = config.description;

    showNarration(config.narration);

    // Branch buttons only make sense on full viewer
    if (branchOptions) {
      if (!EMBED_MODE && nextState === "parents") branchOptions.style.display = "flex";
      else branchOptions.style.display = "none";
    }

    // Unlock after paint
    setTimeout(() => {
      transitionLock = false;
    }, 120);
  }, 160);
}

function animateZoom(className) {
  if (EMBED_MODE) return; // prevent “shake” in preview
  if (!viewerImage) return;

  viewerImage.classList.remove("zoom-in", "zoom-out");
  void viewerImage.offsetWidth;
  viewerImage.classList.add(className);

  setTimeout(() => {
    viewerImage.classList.remove(className);
  }, 700);
}

function zoomIn() {
  if (EMBED_MODE) return;

  if (state === "malik") {
    animateZoom("zoom-in");
    applyState("malik_descendants");
  } else if (state === "malik_descendants") {
    animateZoom("zoom-in");
    applyState("imani");
  } else if (state === "imani") {
    animateZoom("zoom-in");
    applyState("imani_descendants");
  } else if (state === "selah") {
    animateZoom("zoom-in");
    applyState("selah_descendants");
  } else if (state === "parents") {
    if (branchOptions) branchOptions.style.display = "flex";
  }
}

function zoomOut() {
  if (EMBED_MODE) return;

  if (state === "malik") {
    animateZoom("zoom-out");
    applyState("parents");
  } else if (state === "malik_descendants") {
    animateZoom("zoom-out");
    applyState("malik");
  } else if (state === "imani") {
    animateZoom("zoom-out");
    applyState("malik_descendants");
  } else if (state === "imani_descendants") {
    animateZoom("zoom-out");
    applyState("imani");
  } else if (state === "julian") {
    animateZoom("zoom-out");
    applyState("parents");
  } else if (state === "selah") {
    animateZoom("zoom-out");
    applyState("parents");
  } else if (state === "selah_descendants") {
    animateZoom("zoom-out");
    applyState("selah");
  } else if (state === "parents") {
    animateZoom("zoom-in");
    applyState("malik");
  }
}

function selectBranch(branch) {
  if (EMBED_MODE) return;

  if (branch === "julian") {
    animateZoom("zoom-in");
    applyState("julian");
  } else if (branch === "malik") {
    animateZoom("zoom-in");
    applyState("malik");
  } else if (branch === "selah") {
    animateZoom("zoom-in");
    applyState("selah");
  }
}

function resetViewer() {
  if (EMBED_MODE) return;

  if (viewerImage) viewerImage.classList.remove("zoom-in", "zoom-out");
  applyState("malik");
  if (isPlaying) startNarrationAutoAdvance();
}

// Boot
applyState("malik");
startNarrationAutoAdvance();