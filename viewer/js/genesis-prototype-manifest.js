// viewer/js/genesis-prototype-manifest.js
// Public Genesis prototype manifest used only when preview=1.

(() => {
  window.GENESIS_PROTOTYPE_MANIFEST = {
    mode: "preview",
    navigation_mode: "graph",
    hero_kicker: "Genesis Prototype Viewer",
    hero_title: "Malik Moreland Genesis Prototype",
    hero_body:
      "Public preview of the cinematic lineage experience for the Moreland prototype family.",
    instructions:
      "Use Origins and Future Line navigation, then branch options, to move through each lineage layer.",
    path_title: "Prototype Path",
    path_items: [
      "Malik Moreland anchor",
      "Elias and Clara Moreland origins",
      "Malik descendant layer",
      "Imani Moreland adult profile",
      "Imani descendant branch",
      "Selah Carter branch",
      "Julian Moreland branch",
    ],
    nav_labels: {
      left: "Origins",
      right: "Future Line",
    },
    initial_state_id: "malik_anchor",
    controls: {
      allow_lineage_navigation: true,
      allow_zoom: true,
      allow_reset: true,
      allow_narration_auto_advance: true,
      allow_gaze_navigation: true,
      allow_branch_navigation: true,
      max_zoom_layers: 4,
    },
    family: {
      family_name: "Moreland Family",
      anchor_name: "Malik Moreland",
    },
    states: [
      {
        id: "malik_anchor",
        image: "../images/malik.jpg",
        title: "Malik Moreland",
        status: "Genesis anchor",
        node: "Malik Moreland",
        description:
          "Main prototype buyer and anchor. Spouse: Naomi Moreland. Children: Eli Moreland and Imani Moreland.",
        narration:
          "Malik Moreland is the cinematic anchor for this Genesis prototype lineage experience.",
        left_state_id: "moreland_parents",
        right_state_id: "malik_descendants",
        eye_targets: {
          left: { x: 20, y: 50 },
          right: { x: 80, y: 50 },
        },
      },
      {
        id: "moreland_parents",
        image: "../images/parents.jpg",
        title: "Elias Moreland + Clara Moreland",
        status: "Origin node",
        node: "Moreland parents",
        description:
          "Origin of this family line. Children: Malik Moreland, Julian Moreland, and Selah Carter.",
        narration:
          "Elias and Clara Moreland are the root origin for the branch pathways in this preview.",
        left_state_id: "",
        right_state_id: "malik_anchor",
        eye_targets: {
          left: { x: 28, y: 50 },
          right: { x: 72, y: 50 },
        },
      },
      {
        id: "malik_descendants",
        image: "../images/malik_descendants.jpg",
        title: "Malik Descendants",
        status: "Future line",
        node: "Malik descendant branch",
        description:
          "Descendant view of Malik and Naomi's line, including daughter Imani Moreland.",
        narration:
          "From Malik, the future line expands to descendants and then into Imani's adult branch.",
        left_state_id: "malik_anchor",
        right_state_id: "imani_anchor",
        eye_targets: {
          left: { x: 24, y: 50 },
          right: { x: 78, y: 50 },
        },
      },
      {
        id: "imani_anchor",
        image: "../images/imani.jpg",
        title: "Imani Moreland / Imani Benton",
        status: "Adult profile",
        node: "Imani Moreland",
        description:
          "Adult daughter of Malik Moreland and Naomi Moreland. Spouse: Marcus Benton.",
        narration:
          "Imani Moreland appears as the adult anchor for her branch before moving to descendants.",
        left_state_id: "malik_descendants",
        right_state_id: "imani_descendants",
        eye_targets: {
          left: { x: 23, y: 50 },
          right: { x: 77, y: 50 },
        },
      },
      {
        id: "imani_descendants",
        image: "../images/imani_descendants.jpg",
        title: "Imani Descendants",
        status: "Future line",
        node: "Imani descendant branch",
        description:
          "Children of Imani Benton and Marcus Benton: Micah Benton and Zara Benton.",
        narration:
          "Imani's descendants represent the next generation continuity in this public preview.",
        left_state_id: "imani_anchor",
        right_state_id: "",
        eye_targets: {
          left: { x: 24, y: 50 },
          right: { x: 76, y: 50 },
        },
      },
      {
        id: "julian_anchor",
        image: "../images/julian.jpg",
        title: "Julian Moreland",
        status: "Sibling branch",
        node: "Julian Moreland",
        description:
          "Malik's brother. This branch has no descendants in the Genesis prototype.",
        narration:
          "Julian Moreland is a sibling branch with no descendant layer in this prototype.",
        left_state_id: "moreland_parents",
        right_state_id: "",
        eye_targets: {
          left: { x: 25, y: 50 },
          right: { x: 75, y: 50 },
        },
      },
      {
        id: "selah_anchor",
        image: "../images/selah.jpg",
        title: "Selah Carter",
        status: "Sibling branch",
        node: "Selah Carter",
        description:
          "Malik's sister. Spouse: Andre Carter. Child: Camille Carter.",
        narration:
          "Selah Carter is a sibling branch that leads into her own descendant layer.",
        left_state_id: "moreland_parents",
        right_state_id: "selah_descendants",
        eye_targets: {
          left: { x: 23, y: 50 },
          right: { x: 77, y: 50 },
        },
      },
      {
        id: "selah_descendants",
        image: "../images/selah_descendants.jpg",
        title: "Selah Descendants",
        status: "Future line",
        node: "Selah descendant branch",
        description:
          "Descendant layer for Selah Carter and her household line.",
        narration:
          "Selah's branch extends to descendants, then returns back to Selah and to the parents node.",
        left_state_id: "selah_anchor",
        right_state_id: "",
        eye_targets: {
          left: { x: 24, y: 50 },
          right: { x: 76, y: 50 },
        },
      },
    ],
    branch_options_by_state: {
      moreland_parents: [
        { label: "Enter Malik Moreland", target_state_id: "malik_anchor" },
        { label: "Enter Selah Carter", target_state_id: "selah_anchor" },
        { label: "Enter Julian Moreland", target_state_id: "julian_anchor" },
      ],
      malik_anchor: [
        { label: "Zoom Out to Origins", target_state_id: "moreland_parents" },
        { label: "Zoom In to Descendants", target_state_id: "malik_descendants" },
      ],
      malik_descendants: [
        { label: "Enter Imani Moreland", target_state_id: "imani_anchor" },
        { label: "Return to Malik Moreland", target_state_id: "malik_anchor" },
      ],
      imani_anchor: [
        { label: "Zoom In to Imani Descendants", target_state_id: "imani_descendants" },
        { label: "Return to Malik Descendants", target_state_id: "malik_descendants" },
      ],
      imani_descendants: [
        { label: "Return to Imani Moreland", target_state_id: "imani_anchor" },
      ],
      julian_anchor: [
        { label: "Return to Elias and Clara", target_state_id: "moreland_parents" },
      ],
      selah_anchor: [
        { label: "Zoom In to Selah Descendants", target_state_id: "selah_descendants" },
        { label: "Return to Elias and Clara", target_state_id: "moreland_parents" },
      ],
      selah_descendants: [
        { label: "Return to Selah Carter", target_state_id: "selah_anchor" },
      ],
    },
  };
})();
