const slideImg = document.getElementById("slideImg");
const branchButtons = document.getElementById("branch-buttons");
const playPauseBtn = document.getElementById("playPauseBtn");

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
let playing = true;

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
  showSlide(currentIndex + 1);
}

function prevSlide() {
  showSlide(currentIndex - 1);
}

function playSlideshow() {
  if (!interval) {
    interval = setInterval(() => {
      nextSlide();
    }, 6000);
  }
}

function pauseSlideshow() {
  clearInterval(interval);
  interval = null;
}

function togglePlay() {
  if (interval) {
    pauseSlideshow();
    playPauseBtn.innerText = "Play";
  } else {
    playSlideshow();
    playPauseBtn.innerText = "Pause";
  }
}

// Branch Handlers
document.getElementById("btnJulian").onclick = () => {
  branchButtons.style.display = "none";
  slideImg.src = "images/julian.jpg";
  slideImg.className = "zoom-in";
  setTimeout(() => showSlide(1), 6000);
};

document.getElementById("btnMalik").onclick = () => {
  branchButtons.style.display = "none";
  showSlide(2);
  setTimeout(() => showSlide(3), 6000);
  setTimeout(() => showSlide(4), 12000);
  setTimeout(() => showSlide(5), 18000);
  setTimeout(() => showSlide(6), 24000);
};

document.getElementById("btnSelah").onclick = () => {
  branchButtons.style.display = "none";
  slideImg.src = "images/selah.jpg";
  slideImg.className = "zoom-in";
  setTimeout(() => {
    slideImg.src = "images/selah_descendants.jpg";
    slideImg.className = "zoom-in";
    setTimeout(() => showSlide(6), 6000);
  }, 6000);
};

showSlide(0);
playSlideshow();
