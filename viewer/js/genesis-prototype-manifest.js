// viewer/js/genesis-prototype-manifest.js
// Public Genesis prototype manifest used only when preview=1.

(() => {
  window.GENESIS_PROTOTYPE_MANIFEST = {
    mode: "preview",
    navigation_mode: "graph",
    hero_kicker: "Genesis Prototype Viewer",
    hero_title: "Malik Moreland Genesis Prototype",
    hero_body:
      "Confirmed cinematic lineage preview for the approved Genesis Prototype family.",
    instructions:
      "Use gesture zoom navigation only. Zoom out returns to ancestors/parents, zoom in moves to descendants, and select siblings only from the parents photo regions.",
    path_title: "Prototype Path",
    path_items: [
      "Malik Moreland",
      "Elias Moreland + Clara Moreland",
      "Malik descendants",
      "Imani Moreland",
      "Imani descendants",
      "Selah Carter",
      "Selah descendants",
      "Julian Moreland",
    ],
    nav_labels: {
      left: "Parents",
      right: "Descendants",
    },
    initial_state_id: "malik_anchor",
    controls: {
      allow_lineage_navigation: false,
      allow_zoom: false,
      allow_reset: false,
      allow_narration_auto_advance: false,
      allow_gaze_navigation: true,
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
        status: "Genesis anchor",
        node: "Malik Moreland",
        description:
          "Primary Genesis anchor.",
        narration:
          "Malik Moreland is the anchor state for this confirmed Genesis Prototype.",
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
          "Top generation origin with sibling selection regions.",
        narration:
          "Elias Moreland and Clara Moreland are the top generation origin.",
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
        node: "Malik descendants",
        description:
          "Descendant layer following Malik Moreland.",
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
        title: "Imani Moreland",
        status: "Adult profile",
        node: "Imani Moreland",
        description:
          "Imani Moreland adult anchor state.",
        narration:
          "Imani Moreland anchors this branch before descendants.",
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
          "Descendant layer following Imani Moreland.",
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
          "Julian Moreland sibling branch with no descendants available.",
        narration:
          "Julian Moreland has no descendants available in this prototype.",
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
          "Selah Carter sibling branch.",
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
          "Descendant layer following Selah Carter.",
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
})();
