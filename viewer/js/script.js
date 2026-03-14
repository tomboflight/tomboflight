const viewerImage = document.getElementById("viewerImage");
const branchOptions = document.getElementById("branchOptions");

let state = "malik";

function zoomIn() {

viewerImage.classList.add("zoom-in");

setTimeout(() => {
viewerImage.classList.remove("zoom-in");
},800);

if(state === "malik"){

viewerImage.src="../images/malik_descendants.jpg";
state="malik_descendants";

}

else if(state === "malik_descendants"){

viewerImage.src="../images/imani.jpg";
state="imani";

}

else if(state === "imani"){

viewerImage.src="../images/imani_descendants.jpg";
state="imani_descendants";

}

else if(state === "parents"){

branchOptions.style.display="flex";

}

}

function zoomOut(){

viewerImage.classList.add("zoom-out");

setTimeout(()=>{
viewerImage.classList.remove("zoom-out");
},800);

if(state==="malik"){

viewerImage.src="../images/parents.jpg";
state="parents";
branchOptions.style.display="flex";

}

else if(state==="malik_descendants"){

viewerImage.src="../images/malik.jpg";
state="malik";

}

else if(state==="imani"){

viewerImage.src="../images/malik_descendants.jpg";
state="malik_descendants";

}

else if(state==="imani_descendants"){

viewerImage.src="../images/imani.jpg";
state="imani";

}

else if(state==="parents"){

viewerImage.src="../images/malik.jpg";
state="malik";
branchOptions.style.display="none";

}

}

function selectBranch(person){

branchOptions.style.display="none";

if(person==="julian"){

viewerImage.src="../images/julian.jpg";
state="julian";

}

if(person==="selah"){

viewerImage.src="../images/selah.jpg";
state="selah";

}

}

function resetViewer(){

viewerImage.src="../images/malik.jpg";
state="malik";
branchOptions.style.display="none";

}