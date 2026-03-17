const familySelect = document.querySelector("[data-family-select]");
const loadButton = document.querySelector("[data-load-intelligence]");

const statMembers = document.querySelector("[data-stat-members]");
const statRelations = document.querySelector("[data-stat-relations]");
const statGenerations = document.querySelector("[data-stat-generations]");
const statBranches = document.querySelector("[data-stat-branches]");
const summaryBox = document.querySelector("[data-lineage-summary]");

async function loadFamilies(){

const res = await fetch("/families");
const families = await res.json();

families.forEach(family => {

const option = document.createElement("option");
option.value = family._id;
option.textContent = family.family_name;

familySelect.appendChild(option);

});

}

async function analyzeFamily(){

const familyId = familySelect.value;

if(!familyId){
alert("Select a family first.");
return;
}

const res = await fetch(`/families/${familyId}/graph`);
const graph = await res.json();

const members = graph.members.length;
const relations = graph.relationships.length;

let generations = new Set();
let branches = new Set();

graph.members.forEach(member=>{
generations.add(member.generation || 0);

if(member.parent_id){
branches.add(member.parent_id);
}
});

statMembers.textContent = members;
statRelations.textContent = relations;
statGenerations.textContent = generations.size;
statBranches.textContent = branches.size;

summaryBox.innerHTML = `
<p>
This lineage contains <strong>${members}</strong> verified members
connected through <strong>${relations}</strong> relationships
across <strong>${generations.size}</strong> generations.
</p>

<p>
Branching analysis detected <strong>${branches.size}</strong> family branches.
</p>
`;

}

loadButton.addEventListener("click", analyzeFamily);

loadFamilies();