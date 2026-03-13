const slideImg = document.getElementById("slideImg");
const branchButtons = document.getElementById("branch-buttons");
const playPauseBtn = document.getElementById("playPauseBtn");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");

const sequence = [
  { id: "malik", img: "images/malik.jpg", zoom: "zoom-in" },
  { id: "parents", img: "images/parents.jpg", zoom: "zoom-out" },
  { id: "malik-back", img: "images/malik.jpg", zoom: "zoom-in" },
  { id: "malik-desc", img: "images/malik_descendants.jpg", zoom: "zoom-in" },
  { id: "imani", img: "images/imani.jpg", zoom: "zoom-in" },
  { id: "imani-desc", img: "images/imani_descendants.jpg", zoom: "zoom-in" },
  { id: "return-parents", img: "images/parents.jpg", zoom: "zoom-out" },
];

let currentIndex = 0;
let interval = null;
let isPlaying = false;
const pendingTimeouts = [];

function showSlide(index) {
  if (index < 0 || index >= sequence.length) return;
  currentIndex = index;
  const slide = sequence[index];
  slideImg.src = slide.img;
  slideImg.className = slide.zoom;
  if (slide.id === "parents" || slide.id === "return-parents") {
    pauseSlideshow();
    branchButtons.style.display = "flex";
  } else {
    branchButtons.style.display = "none";
  }
}

function nextSlide() {
  if (currentIndex < sequence.length - 1) {
    showSlide(currentIndex + 1);
  } else {
    showSlide(0);
  }
}

function prevSlide() {
  if (currentIndex > 0) {
    showSlide(currentIndex - 1);
  } else {
    showSlide(sequence.length - 1);
  }
}

function playSlideshow() {
  if (!interval) {
    isPlaying = true;
    interval = setInterval(() => nextSlide(), 6000);
    playPauseBtn.textContent = "Pause";
  }
}

function pauseSlideshow() {
  if (interval) {
    clearInterval(interval);
    interval = null;
    isPlaying = false;
    playPauseBtn.textContent = "Play";
  }
}

function togglePlay() {
  interval ? pauseSlideshow() : playSlideshow();
}

function clearPendingTimeouts() {
  pendingTimeouts.forEach(id => clearTimeout(id));
  pendingTimeouts.length = 0;
}

function setTrackedTimeout(fn, delay) {
  const id = setTimeout(fn, delay);
  pendingTimeouts.push(id);
  return id;
}

function handleJulian() {
  clearPendingTimeouts();
  pauseSlideshow();
  branchButtons.style.display = "none";
  slideImg.src = "images/julian.jpg";
  slideImg.className = "zoom-in";
  setTrackedTimeout(() => showSlide(1), 6000);
}

function handleMalik() {
  clearPendingTimeouts();
  pauseSlideshow();
  branchButtons.style.display = "none";
  showSlide(2);
  setTrackedTimeout(() => showSlide(3), 6000);
  setTrackedTimeout(() => showSlide(4), 12000);
  setTrackedTimeout(() => showSlide(5), 18000);
  setTrackedTimeout(() => showSlide(6), 24000);
}

function handleSelah() {
  clearPendingTimeouts();
  pauseSlideshow();
  branchButtons.style.display = "none";
  slideImg.src = "images/selah.jpg";
  slideImg.className = "zoom-in";
  setTrackedTimeout(() => {
    slideImg.src = "images/selah_descendants.jpg";
    slideImg.className = "zoom-in";
    setTrackedTimeout(() => showSlide(6), 6000);
  }, 6000);
}

document.getElementById("btnJulian").addEventListener("click", handleJulian);
document.getElementById("btnMalik").addEventListener("click", handleMalik);
document.getElementById("btnSelah").addEventListener("click", handleSelah);

prevBtn.addEventListener("click", prevSlide);
playPauseBtn.addEventListener("click", togglePlay);
nextBtn.addEventListener("click", nextSlide);

window.addEventListener("beforeunload", () => {
  clearPendingTimeouts();
  pauseSlideshow();
});

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    showSlide(0);
    setTimeout(() => playSlideshow(), 500);
  });
} else {
  showSlide(0);
  setTimeout(() => playSlideshow(), 500);
}
