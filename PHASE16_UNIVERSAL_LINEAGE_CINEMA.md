# Phase 16 — Universal Lineage Cinema

Phase 16 turns the Moreland prototype behavior into a private, data-driven
viewer for every eligible Tomb of Light household and linked family network.
It does not copy the Moreland people or hard-code a customer sequence.

## Publication contract

A member receives a cinematic slide only when the selected portrait is:

1. a `member_photo` assigned to that exact project, family, and member;
2. clean from malware scanning and outside quarantine;
3. backed by consent and authority attestations;
4. approved for verification, consent, and cinematic use by the master review;
5. not pending deletion; and
6. available through authenticated private delivery.

The named member dropbox creates the assignment. Master approval updates the
member's single approved-photo pointer. The next authenticated viewer request
then compiles the current approved portraits and relationships into the family
tour automatically. Rejected, revoked, quarantined, unapproved, deleted, or
unshared portraits are not compiled.

## Family graph contract

The compiler understands every relationship type in the canonical relationship
catalog. It groups them without changing their meaning:

- parent and elder types navigate as ancestry;
- spouses, domestic partners, former partners, and co-parents navigate as partners;
- sibling types navigate as sibling branches;
- cousins, aunts/uncles, godparents, mentors, in-laws, friends, household
  members, identity bridges, and linked-household bridges navigate as extended
  branches;
- biological/verified links render solid, adoptive links double, step/foster/
  guardian/chosen links dashed, narrative links dotted, and former partnerships
  historical.

Pending, disputed, rejected, revoked, and deleted relationships cannot enter a
published tour. The family placement service remains the source of generation
alignment; the compiler reports unplaced states instead of silently changing a
person's generation.

## Tour contract

One member is one content state. A tour step is one visit to a state. The tour
may revisit an anchor or ancestor to move between branches, but every visit has
a unique step id. That distinction prevents the old repeated-state cursor bug.

Every compilation must be:

- deterministic for the same approved graph;
- anchored on the primary member when that portrait is approved;
- complete across every approved portrait;
- bounded to at most four tour steps per eligible state;
- safe for disconnected/unplaced members without inventing ancestry; and
- navigable through parent, child, partner, sibling, and extended-branch controls.

The full tour—not the previous six-item preview cap—is returned as
`auto_advance_state_ids`, `tour_steps`, and `path_items`.

## Linked Family Key contract

The network viewer uses the existing approved household-link graph and its
generation offsets. Another household contributes a member, relationship, or
portrait only when that household explicitly exposes it to linked families.
Private, internal-only, unapproved, or orphan relationship data is filtered
before compilation.

An external household is not placed from its local generation alone. Linked
members without a resolved network generation offset are excluded, and any
alignment conflict blocks linked-branch compilation while leaving the root
household viewer available. This prevents a Family Key from shifting an entire
branch into the wrong generation.

Linked portraits use a dedicated viewer authorization path. A caller must be
authorized for the root network project, the portrait must appear in that
caller's current privacy-filtered network, and its member/project provenance
must still match. Guessing an upload id or root project query cannot unlock it.

Family Keys never share passwords, sessions, vault files, billing control, or
unrelated private records. They connect approved graph projections only.

## Private versioning contract

Each compiled private manifest receives a canonical SHA-256 content hash. The
immutable version is inserted before a one-document active pointer is swapped.
If pointer activation fails, the prior active pointer remains unchanged and the
new manifest is not returned as active.

Unique startup indexes enforce one version key and one active pointer per
project. Index creation is part of production startup and fails closed with the
other critical controls.

These versions are private operational records. They are not NFT metadata and
do not make family portraits or relationships public.

## Viewer behavior

Family slideshow playback is independent of the paid narration entitlement.
Every complete multi-slide family manifest can autoplay. Narration text remains
hidden unless the package includes narration. Manual tree navigation pauses the
slideshow, and the customer can resume it with a clearly labeled control.

The same graph behavior now applies to dynamic customer manifests and the public
prototype: full-path autoplay, graph-aware zoom controls, branch choices, gaze
navigation, and duplicate-step-safe path highlighting.

## Verification coverage

Phase 16 includes tests for:

- the full Moreland-style multi-branch topology;
- all canonical family relationship types;
- repeated routing states and unique tour steps;
- hidden-parent sibling derivation;
- pending/disputed relationship exclusion;
- deterministic output under reversed database order;
- 250-member and maximum 999-member lineage depth;
- immutable manifest versioning and pointer failure behavior;
- household and linked-network manifest integration;
- linked portrait privacy and provenance failures;
- autoplay without narration; and
- dynamic graph navigation in Chromium.
