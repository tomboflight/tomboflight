const viewerImage = document.getElementById("viewerImage");
const branchOptions = document.getElementById("branchOptions");
const viewerTitle = document.getElementById("viewerTitle");
const viewerStatus = document.getElementById("viewerStatus");
const currentNode = document.getElementById("currentNode");
const currentDescription = document.getElementById("currentDescription");

const states = {
  malik: {
    image: "images/malik.jpg",
    title: "Malik Moreland",
    status: "Anchor Portrait",
    node: "Malik Moreland",
    description: "Starting at the anchor portrait for the Genesis family line."
  },
  parents: {
    image: "images/parents.jpg",
    title: "Elias & Clara Moreland",
    status: "Parent Structure",
    node: "Parent Layer",
    description: "Choose a family branch from the shared parent structure."
  },
  malik_descendants: {
    image: "images/malik_descendants.jpg",
    title: "Malik Descendants",
    status: "Descendant Layer",
    node: "Malik Descendants",
    description: "Malik's line expands into the next generation."
  },
  imani: {
    image: "images/imani.jpg",
    title: "Imani Moreland",
    status: "Next Generation Anchor",
    node: "Imani Moreland",
    description: "Imani becomes the next generation anchor portrait."
  },
  imani_descendants: {
    image: "images/imani_descendants.jpg",
    title: "Imani Descendants",
    status: "Future Legacy Layer",
    node: "Imani Descendants",
    description: "Imani's descendants extend the family line forward."
  },
  julian: {
    image: "images/julian.jpg",
    title: "Julian Moreland",
    status: "Sibling Branch",
    node: "Julian Moreland",
    description: "Julian is a sibling branch with no descendant layer."
  },
  selah: {
    image: "images/selah.jpg",
    title: "Selah Carter",
    status: "Sibling Branch",
    node: "Selah Carter",
    description: "Selah is a sibling branch with her own descendants."
  },
  selah_descendants: {
    image: "images/selah_descendants.jpg",
    title: "Selah Descendants",
    status: "Descendant Layer",
    node: "Selah Descendants",
    description: "Selah's line expands into her descendant branch."
  }
};

let state = "malik";

function applyState(nextState) {
  const config = states[nextState];
  if (!config) return;

  state = nextState;
  viewerImage.style.opacity = "0.35";

  setTimeout(() => {
    viewerImage.src = config.image;
    viewerImage.alt = config.node;
    viewerTitle.textContent = config.title;
    viewerStatus.textContent = config.status;
    currentNode.textContent = config.node;
    currentDescription.textContent = config.description;

    viewerImage.classList.remove("zoom-in", "zoom-out");
    viewerImage.style.opacity = "1";
  }, 160);

  if (nextState === "parents") {
    branchOptions.style.display = "flex";
  } else {
    branchOptions.style.display = "none";
  }
}

function animateZoom(className) {
  viewerImage.classList.remove("zoom-in", "zoom-out");
  void viewerImage.offsetWidth;
  viewerImage.classList.add(className);

  setTimeout(() => {
    viewerImage.classList.remove(className);
  }, 700);
}

function zoomIn() {
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
    branchOptions.style.display = "flex";
  }
}

function zoomOut() {
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
  viewerImage.classList.remove("zoom-in", "zoom-out");
  applyState("malik");
}

applyState("malik");