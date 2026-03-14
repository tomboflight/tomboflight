const slideImg = document.getElementById("slideImg");
const branchButtons = document.getElementById("branch-buttons");
const playPauseBtn = document.getElementById("playPauseBtn");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");

const viewerTitle = document.getElementById("viewerTitle");
const viewerStatus = document.getElementById("viewerStatus");
const currentNode = document.getElementById("currentNode");
const currentDescription = document.getElementById("currentDescription");

const sequence = [
  {
    id: "malik",
    img: "images/malik.jpg",
    zoom: "zoom-in",
    title: "Anchor Portrait",
    status: "Malik Moreland Line",
    node: "Malik Moreland",
    description: "Starting at the central anchor portrait for the Genesis lineage experience."
  },
  {
    id: "parents",
    img: "images/parents.jpg",
    zoom: "zoom-out",
    title: "Parent Structure",
    status: "Shared Parent Layer",
    node: "Elias & Clara Moreland",
    description: "The parent structure acts as the central branching point for the family lines."
  },
  {
    id: "malik-back",
    img: "images/malik.jpg",
    zoom: "zoom-in",
    title: "Return to Anchor",
    status: "Malik Moreland Line",
    node: "Malik Moreland",
    description: "Returning to the anchor portrait before moving deeper into descendants."
  },
  {
    id: "malik-desc",
    img: "images/malik_descendants.jpg",
    zoom: "zoom-in",
    title: "Descendant Branches",
    status: "Descendant Layer",
    node: "Malik Descendants",
    description: "The lineage expands into children and connected future branches."
  },
  {
    id: "imani",
    img: "images/imani.jpg",
    zoom: "zoom-in",
    title: "Next Generation Anchor",
    status: "Imani Branch",
    node: "Imani Moreland",
    description: "A next-generation anchor portrait for the evolving family story."
  },
  {
    id: "imani-desc",
    img: "images/imani_descendants.jpg",
    zoom: "zoom-in",
    title: "Future Legacy Layers",
    status: "Extended Legacy Branch",
    node: "Imani Descendants",
    description: "The viewer continues into future descendants and deeper lineage expansion."
  },
  {
    id: "return-parents",
    img: "images/parents.jpg",
    zoom: "zoom-out",
    title: "Branch Selection",
    status: "Shared Parent Layer",
    node: "Choose a Family Branch",
    description: "From the parents layer, choose Julian, Malik, or Selah to continue the experience."
  }
];

let currentIndex = 0;
let interval = null;
let branchTimeouts = [];
let playing = true;

function clearBranchTimeouts() {
  branchTimeouts.forEach(timeoutId => clearTimeout(timeoutId));
  branchTimeouts = [];
}

function updateInfo(slide) {
  if (viewerTitle) viewerTitle.textContent = slide.title;
  if (viewerStatus) viewerStatus.textContent = slide.status;
  if (currentNode) currentNode.textContent = slide.node;
  if (currentDescription) currentDescription.textContent = slide.description;
}

function showSlide(index) {
  if (index < 0 || index >= sequence.length) return;

  clearBranchTimeouts();
  currentIndex = index;

  const slide = sequence[index];

  slideImg.style.opacity = "0.35";

  setTimeout(() => {
    slideImg.src = slide.img;
    slideImg.className = slide.zoom;
    slideImg.alt = slide.node;
    updateInfo(slide);
    slideImg.style.opacity = "1";
  }, 180);

  if (slide.id === "parents" || slide.id === "return-parents") {
    pauseSlideshow();
    branchButtons.style.display = "flex";
  } else {
    branchButtons.style.display = "none";
  }
}

function nextSlide() {
  if (currentIndex >= sequence.length - 1) {
    pauseSlideshow();
    playPauseBtn.innerText = "Play";
    return;
  }

  showSlide(currentIndex + 1);
}

function prevSlide() {
  if (currentIndex <= 0) return;
  showSlide(currentIndex - 1);
}

function playSlideshow() {
  clearBranchTimeouts();

  if (!interval) {
    interval = setInterval(() => {
      if (currentIndex >= sequence.length - 1) {
        pauseSlideshow();
        playPauseBtn.innerText = "Play";
        return;
      }
      nextSlide();
    }, 6000);
  }

  playing = true;
}

function pauseSlideshow() {
  clearInterval(interval);
  interval = null;
  playing = false;
}

function togglePlay() {
  interval ? pauseSlideshow() : playSlideshow();
}

document.getElementById("btnJulian").onclick = () => {
  clearBranchTimeouts();
  branchButtons.style.display = "none";
  pauseSlideshow();
  playPauseBtn.innerText = "Play";

  slideImg.style.opacity = "0.35";

  setTimeout(() => {
    slideImg.src = "images/julian.jpg";
    slideImg.className = "zoom-in";
    slideImg.alt = "Julian Moreland";

    if (viewerTitle) viewerTitle.textContent = "Sibling Branch";
    if (viewerStatus) viewerStatus.textContent = "Julian Moreland Line";
    if (currentNode) currentNode.textContent = "Julian Moreland";
    if (currentDescription) {
      currentDescription.textContent =
        "Julian's branch is a direct sibling route from the shared parent structure.";
    }

    slideImg.style.opacity = "1";
  }, 180);

  const timeoutId = setTimeout(() => showSlide(1), 6000);
  branchTimeouts.push(timeoutId);
};

document.getElementById("btnMalik").onclick = () => {
  clearBranchTimeouts();
  branchButtons.style.display = "none";
  pauseSlideshow();
  playPauseBtn.innerText = "Play";

  showSlide(2);

  branchTimeouts.push(setTimeout(() => showSlide(3), 6000));
  branchTimeouts.push(setTimeout(() => showSlide(4), 12000));
  branchTimeouts.push(setTimeout(() => showSlide(5), 18000));
  branchTimeouts.push(setTimeout(() => showSlide(6), 24000));
};

document.getElementById("btnSelah").onclick = () => {
  clearBranchTimeouts();
  branchButtons.style.display = "none";
  pauseSlideshow();
  playPauseBtn.innerText = "Play";

  slideImg.style.opacity = "0.35";

  setTimeout(() => {
    slideImg.src = "images/selah.jpg";
    slideImg.className = "zoom-in";
    slideImg.alt = "Selah Carter";

    if (viewerTitle) viewerTitle.textContent = "Sibling Branch";
    if (viewerStatus) viewerStatus.textContent = "Selah Carter Line";
    if (currentNode) currentNode.textContent = "Selah Carter";
    if (currentDescription) {
      currentDescription.textContent =
        "Selah's branch extends from the shared parent structure into her own descendants.";
    }

    slideImg.style.opacity = "1";
  }, 180);

  branchTimeouts.push(
    setTimeout(() => {
      slideImg.style.opacity = "0.35";

      setTimeout(() => {
        slideImg.src = "images/selah_descendants.jpg";
        slideImg.className = "zoom-in";
        slideImg.alt = "Selah descendants";

        if (viewerTitle) viewerTitle.textContent = "Descendant Branches";
        if (viewerStatus) viewerStatus.textContent = "Selah Descendants";
        if (currentNode) currentNode.textContent = "Selah Descendants";
        if (currentDescription) {
          currentDescription.textContent =
            "Selah's lineage expands into the next family layer before returning to the parent structure.";
        }

        slideImg.style.opacity = "1";
      }, 180);

      branchTimeouts.push(setTimeout(() => showSlide(6), 6000));
    }, 6000)
  );
};

showSlide(0);
playSlideshow();
