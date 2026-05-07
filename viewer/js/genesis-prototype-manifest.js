// viewer/js/genesis-prototype-manifest.js
// Public demo-safe manifest data for viewer demo routes.

(() => {
  const MALIK_MORELAND_DEMO_MANIFEST = {
    mode: "demo",
    navigation_mode: "graph",
    hero_kicker: "Sample demo tree",
    hero_title: "See a family lineage come alive.",
    hero_body:
      "Start at Malik, travel to parents, return to Malik, then follow descendants and sibling branches.",
    instructions:
      "Demo-safe family data for public preview. Current view: Malik Moreland",
    path_title: "Moreland demo flow",
    path_items: [
      "Malik Moreland",
      "Elias Moreland + Clara Moreland",
      "Return to Malik",
      "Malik descendants",
      "Imani Benton / Imani Moreland",
      "Imani descendants",
      "Return to Elias + Clara",
      "Selah Carter",
      "Selah descendants",
      "Return to Elias + Clara",
      "Julian Moreland",
    ],
    auto_advance_state_ids: [
      "malik_anchor",
      "moreland_parents",
      "malik_anchor",
      "malik_descendants",
      "imani_anchor",
      "imani_descendants",
      "moreland_parents",
      "selah_anchor",
      "selah_descendants",
      "moreland_parents",
      "julian_anchor",
    ],
    nav_labels: {
      left: "Parents",
      right: "Descendants",
    },
    initial_state_id: "malik_anchor",
    controls: {
      allow_lineage_navigation: true,
      allow_zoom: true,
      allow_reset: false,
      allow_narration_auto_advance: true,
      allow_gaze_navigation: false,
      allow_branch_navigation: false,
      max_zoom_layers: 4,
    },
    family: {
      family_name: "Moreland Family",
      anchor_name: "Malik Moreland",
    },
    parent_overlay: {
      enabled_on_state_id: "moreland_parents",
      hide_delay_ms: 5000,
      regions: [
        { region: "left", label: "Selah Carter", target_state_id: "selah_anchor" },
        { region: "center", label: "Malik Moreland", target_state_id: "malik_anchor" },
        { region: "right", label: "Julian Moreland", target_state_id: "julian_anchor" },
      ],
    },
    states: [
      {
        id: "malik_anchor",
        image: "../images/malik.jpg",
        title: "Malik Moreland",
        status: "Start node",
        node: "Malik Moreland",
        description:
          "Start at Malik Moreland. Zoom out to Elias + Clara Moreland or zoom in to Malik descendants.",
        narration:
          "Malik Moreland is the demo start node.",
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
        node: "Elias Moreland + Clara Moreland",
        description:
          "Top generation origin. Select Malik Moreland, Julian Moreland, or Selah Carter.",
        narration:
          "Elias Moreland and Clara Moreland are the origin generation.",
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
        status: "Malik household",
        node: "Malik descendants",
        description:
          "Malik household: Malik Moreland, Naomi Moreland, Eli Moreland, and Imani Moreland.",
        narration:
          "Zooming in from Malik enters the Malik descendants layer.",
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
        title: "Imani Benton / Imani Moreland",
        status: "Imani adult household",
        node: "Imani Benton / Imani Moreland",
        description:
          "Imani adult household: Imani Benton / Imani Moreland, Marcus Benton, Micah Benton, and Zara Benton.",
        narration:
          "Imani Benton, also Imani Moreland, anchors this branch before descendants.",
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
        node: "Imani descendants",
        description:
          "Descendant layer following Imani Benton / Imani Moreland.",
        narration:
          "Imani descendants are the final zoom-in node for this branch.",
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
          "Julian Moreland has no descendant layer in this demo.",
        narration:
          "Julian Moreland has no descendant layer in this demo.",
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
          "Selah Carter branch with descendants Andre Carter and Camille Carter.",
        narration:
          "Selah Carter leads to one descendant layer.",
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
        node: "Selah descendants",
        description:
          "Selah descendants include Andre Carter and Camille Carter.",
        narration:
          "Selah descendants return to Selah, then to the parents state.",
        left_state_id: "selah_anchor",
        right_state_id: "",
        eye_targets: {
          left: { x: 24, y: 50 },
          right: { x: 76, y: 50 },
        },
      },
    ],
    branch_options_by_state: {},
  };

  window.PUBLIC_DEMO_MANIFESTS = Object.freeze({
    "malik-moreland": MALIK_MORELAND_DEMO_MANIFEST,
  });
  window.GENESIS_PROTOTYPE_MANIFEST = MALIK_MORELAND_DEMO_MANIFEST;
})();
