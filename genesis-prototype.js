const STATES = {
  malik: {
    id: "malik",
    title: "Malik Moreland",
    description: "Malik is the narrative anchor for the Moreland line. Zoom in to discover his children and the digital legacies they carry forward.",
    image: "malik.jpg",
    zoomIn: "malik_descendants",
    zoomOut: "parents",
  },
  malik_descendants: {
    id: "malik_descendants",
    title: "Malik’s Descendants",
    description: "A closer look at the branches Malik started. Pan through names, dates, and stories that highlight the family’s next chapter.",
    image: "malik_descendants.jpg",
    zoomIn: "imani",
    zoomOut: "malik",
  },
  imani: {
    id: "imani",
    title: "Imani Moreland",
    description: "Imani bridges Malik’s generation and the modern stewards of the Moreland legacy.",
    image: "imani.jpg",
    zoomIn: "imani_descendants",
    zoomOut: "malik_descendants",
  },
  imani_descendants: {
    id: "imani_descendants",
    title: "Imani’s Descendants",
    description: "Stories of mentorship, migration, and milestones appear as you continue exploring Imani’s branch.",
    image: "imani_descendants.jpg",
    zoomOut: "imani",
  },
  julian: {
    id: "julian",
    title: "Julian Moreland",
    description: "Julian keeps the family’s artistic traditions alive. Explore to see the creatives who flourish in his wake.",
    image: "julian.jpg",
    zoomOut: "parents",
  },
  selah: {
    id: "selah",
    title: "Selah Carter",
    description: "Selah’s branch honors the Carter lineage and its connection to the Morelands.",
    image: "selah.jpg",
    zoomIn: "selah_descendants",
    zoomOut: "parents",
  },
  selah_descendants: {
    id: "selah_descendants",
    title: "Selah’s Descendants",
    description: "Keep zooming to meet the next generation of Carter storytellers and scholars.",
    image: "selah_descendants.jpg",
    zoomOut: "selah",
  },
  parents: {
    id: "parents",
    title: "The Moreland-Carter Parents",
    description: "Start here to pick a branch. Hover or tap a name tag to jump directly to a sibling’s story.",
    image: "parents.jpg",
    zoomIn: "malik",
    zones: {
      julian: { target: "julian", label: "Julian Moreland", position: { left: "18%", top: "15%" }, hotkey: "1" },
      malik: { target: "malik", label: "Malik Moreland", position: { left: "48%", top: "16%" }, hotkey: "2" },
      selah: { target: "selah", label: "Selah Carter", position: { left: "78%", top: "17%" }, hotkey: "3" },
    },
  },
};

const INITIAL_STATE = "malik";
const TRANSITION_DELAY = 260;
const TRANSITION_BUFFER = 120;

const imageWrapper = document.getElementById("imageWrapper");
const image = document.getElementById("nftImage");
const stateChip = document.getElementById("stateChip");
const stateDescription = document.getElementById("stateDescription");
const spinner = document.getElementById("loadingSpinner");
const zoomInBtn = document.getElementById("zoomInBtn");
const zoomOutBtn = document.getElementById("zoomOutBtn");
const toast = document.getElementById("toast");
const instructionsText = document.getElementById("instructionsText");

const zoneElements = {
  julian: document.getElementById("zone-julian"),
  malik: document.getElementById("zone-malik"),
  selah: document.getElementById("zone-selah"),
};

let currentState = null;
let transitioning = false;
let initialPinchDistance = null;
let lastTapTime = 0;

const imageCache = new Map();

function preloadImage(src) {
  if (imageCache.has(src)) {
    return imageCache.get(src);
  }

  const promise = new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(src);
    img.onerror = () => reject(new Error(`Failed to load image: ${src}`));
    img.src = src;
  });

  imageCache.set(src, promise);
  return promise;
}

function showToast(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
    toast.hidden = true;
  }, 4000);
}

function updateZones(stateId) {
  const state = STATES[stateId];
  const zones = state?.zones ?? {};

  Object.entries(zoneElements).forEach(([key, el]) => {
    const zoneConfig = zones[key];
    if (zoneConfig) {
      el.hidden = false;
      el.style.left = zoneConfig.position?.left ?? "50%";
      el.style.top = zoneConfig.position?.top ?? "12%";
      el.textContent = zoneConfig.label;
      el.dataset.target = zoneConfig.target;
      if (zoneConfig.hotkey) {
        el.dataset.hotkey = zoneConfig.hotkey;
        el.setAttribute("data-hotkey", `⌨ ${zoneConfig.hotkey}`);
      } else {
        delete el.dataset.hotkey;
        el.removeAttribute("data-hotkey");
      }
    } else {
      el.hidden = true;
      delete el.dataset.target;
      delete el.dataset.hotkey;
      el.removeAttribute("data-hotkey");
    }
  });
}

function updateControls(stateId) {
  const state = STATES[stateId];
  const zoomInAvailable = Boolean(state?.zoomIn);
  const zoomOutAvailable = Boolean(state?.zoomOut);

  zoomInBtn.disabled = !zoomInAvailable;
  zoomOutBtn.disabled = !zoomOutAvailable;

  const instructions = [];
  if (zoomInAvailable) instructions.push("Zoom in to explore deeper");
  if (zoomOutAvailable) instructions.push("Zoom out to revisit ancestors");
  if (state?.zones) instructions.push("Tap a name tag to jump to a branch");

  if (instructions.length > 0) {
    instructionsText.textContent = `${instructions.join(" · ")}. Use scroll, pinch, keyboard arrows, or the onscreen controls to explore the family tree.`;
  } else {
    instructionsText.textContent = "Use scroll, pinch, keyboard arrows, or the onscreen controls to explore the family tree.";
  }
}

function updateStateChip(stateId) {
  const state = STATES[stateId];
  stateChip.textContent = state?.title ?? "";
}

function updateDescription(stateId) {
  const state = STATES[stateId];
  stateDescription.textContent = state?.description ?? "";
}

function preloadNeighbors(stateId) {
  const neighbors = new Set();
  const state = STATES[stateId];
  if (!state) return;

  if (state.zoomIn) neighbors.add(state.zoomIn);
  if (state.zoomOut) neighbors.add(state.zoomOut);

  if (state.zones) {
    Object.values(state.zones).forEach((zone) => neighbors.add(zone.target));
  }

  neighbors.forEach((neighborId) => {
    const neighbor = STATES[neighborId];
    if (neighbor?.image) {
      preloadImage(neighbor.image).catch(() => {
        /* handled on demand */
      });
    }
  });
}

function setImageAttributes(stateId) {
  const state = STATES[stateId];
  if (!state) return;

  image.alt = `${state.title} family tree portrait`;
}

async function transitionTo(stateId, reason = "navigate") {
  if (transitioning || stateId === currentState) return;
  const state = STATES[stateId];
  if (!state) return;

  transitioning = true;
  imageWrapper.classList.add("is-transitioning");
  imageWrapper.classList.toggle("zooming-in", reason === "zoomIn");
  imageWrapper.classList.toggle("zooming-out", reason === "zoomOut");
  spinner.setAttribute("aria-hidden", "false");

  try {
    await Promise.all([
      preloadImage(state.image),
      new Promise((resolve) => setTimeout(resolve, TRANSITION_DELAY)),
    ]);
  } catch (error) {
    showToast(error.message);
    spinner.setAttribute("aria-hidden", "true");
    imageWrapper.classList.remove("is-transitioning", "zooming-in", "zooming-out");
    transitioning = false;
    return;
  }

  await new Promise((resolve) => setTimeout(resolve, TRANSITION_BUFFER));

  image.src = state.image;
  imageWrapper.dataset.state = state.id;
  currentState = stateId;
  setImageAttributes(stateId);
  updateStateChip(stateId);
  updateDescription(stateId);
  updateZones(stateId);
  updateControls(stateId);
  preloadNeighbors(stateId);

  requestAnimationFrame(() => {
    imageWrapper.classList.remove("is-transitioning", "zooming-in", "zooming-out");
    spinner.setAttribute("aria-hidden", "true");
    transitioning = false;
  });
}

function zoomIn() {
  const next = STATES[currentState]?.zoomIn;
  if (next) {
    transitionTo(next, "zoomIn");
  }
}

function zoomOut() {
  const next = STATES[currentState]?.zoomOut;
  if (next) {
    transitionTo(next, "zoomOut");
  }
}

function handleWheel(event) {
  event.preventDefault();
  if (transitioning) return;

  if (event.deltaY < 0) {
    zoomIn();
  } else if (event.deltaY > 0) {
    zoomOut();
  }
}

function handleKeydown(event) {
  if (transitioning) return;
  const key = event.key.toLowerCase();

  if (key === "arrowup" || key === "w") {
    event.preventDefault();
    zoomIn();
    return;
  }

  if (key === "arrowdown" || key === "s") {
    event.preventDefault();
    zoomOut();
    return;
  }

  if (key >= "1" && key <= "9") {
    const zoneEntry = Object.values(STATES.parents.zones ?? {}).find((zone) => zone.hotkey === key);
    if (zoneEntry && currentState === "parents") {
      event.preventDefault();
      transitionTo(zoneEntry.target, "hotkey");
    }
  }

  if (key === "enter") {
    event.preventDefault();
    zoomIn();
  }
}

function getTouchDistance(touches) {
  if (touches.length < 2) return 0;
  const [t1, t2] = touches;
  const dx = t2.clientX - t1.clientX;
  const dy = t2.clientY - t1.clientY;
  return Math.hypot(dx, dy);
}

function handleTouchStart(event) {
  if (event.touches.length === 2) {
    initialPinchDistance = getTouchDistance(event.touches);
  }
}

function handleTouchMove(event) {
  if (transitioning || event.touches.length < 2 || initialPinchDistance === null) return;
  const distance = getTouchDistance(event.touches);
  const delta = distance - initialPinchDistance;

  if (Math.abs(delta) > 40) {
    if (delta > 0) {
      zoomOut();
    } else {
      zoomIn();
    }
    initialPinchDistance = null;
  }
}

function handleTouchEnd(event) {
  if (event.touches.length === 0) {
    initialPinchDistance = null;
  }

  const now = Date.now();
  if (now - lastTapTime < 300) {
    zoomIn();
    lastTapTime = 0;
  } else {
    lastTapTime = now;
  }
}

function registerZoneHandlers() {
  Object.values(zoneElements).forEach((element) => {
    element.addEventListener("click", () => {
      if (!element.dataset.target) return;
      transitionTo(element.dataset.target, "zone");
    });
  });
}

function initialise() {
  registerZoneHandlers();
  imageWrapper.addEventListener("wheel", handleWheel, { passive: false });
  imageWrapper.addEventListener("touchstart", handleTouchStart, { passive: true });
  imageWrapper.addEventListener("touchmove", handleTouchMove, { passive: true });
  imageWrapper.addEventListener("touchend", handleTouchEnd, { passive: true });
  imageWrapper.addEventListener("dblclick", (event) => {
    event.preventDefault();
    zoomIn();
  });

  zoomInBtn.addEventListener("click", zoomIn);
  zoomOutBtn.addEventListener("click", zoomOut);
  window.addEventListener("keydown", handleKeydown);

  image.addEventListener("error", () => {
    showToast("We couldn’t load that portrait. Please try again later.");
  });

  preloadImage(STATES[INITIAL_STATE].image)
    .then(() => {
      transitionTo(INITIAL_STATE);
    })
    .catch((error) => {
      showToast(error.message);
    });
}

initialise();
