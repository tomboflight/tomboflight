# Tomb of Light Family Operating Model

Status: Phase 13 implementation contract  
Source design reviewed: `verified and narrative breakdown-3.pdf` (53 pages)

## Product promise

Tomb of Light is a network of independently controlled household trees. A
household owns and edits its own records, connects to another household only by
a two-sided Family Key handshake, and shares only the records explicitly made
available at that boundary. Private family files, passwords, MFA data, wallet
secrets, and the detailed living-person record stay out of linked-family views
and out of public NFT metadata.

The operating sequence is:

`signup/provisioning -> family intake -> people -> relationships -> automatic placement -> named portrait dropboxes -> security scan -> master review -> tree + cinematic slides -> family review -> mint readiness -> blockchain anchor -> continuity`

## Truth and privacy layers

| Layer | Meaning | Enforcement |
| --- | --- | --- |
| Verified Tree | A relationship supported by an approved family record | Requires at least one `verification_evidence` upload that is clean, not quarantined, and master-approved |
| Narrative Tree | Lived, family-held, cultural, step, guardian, adoptive, or chosen-family truth | Clearly marked `narrative`; it cannot claim the verified marker |
| Privacy | Who may see the relationship or person | Owner-only, owner/co-owner, household-private, branch-shared, linked-family-shared, public memorial, or minor-protected |

A death flag never overrides privacy. Public memorial sharing must still be an
explicit privacy choice.

## Relationship coverage and direction

Inside one household, every ancestry record is canonical: **source is the
parent/elder and target is the child/younger-generation member**. Child labels
are derived from that edge. This avoids contradictory parent and child records
for the same fact.

| Group | Supported relationship types |
| --- | --- |
| Biological and reproductive parents | Biological parent, gestational parent, donor parent, intended parent |
| Legal and caregiving parents | Adoptive parent, foster parent, step-parent, guardian |
| Narrative parents | Chosen parent, community parent, spiritual parent |
| Partners | Spouse, former spouse, domestic partner, former partner, co-parent |
| Siblings and peers | Sibling, half-sibling, step-sibling, adoptive sibling, chosen sibling, cousin |
| Extended family | Grandparent, aunt/uncle, in-law, other relative |
| Cultural and community | Godparent, mentor, clan/cultural elder, spiritual elder, family friend, household member |
| Technical graph links | Same-person identity bridge, linked-household bridge |

The customer form spells out `parent -> child`, including
`step-parent -> stepchild`, and uses member selectors rather than typed database
IDs. The add-member form provides two guided parent/guardian boxes and one
partner box.

For cross-household links, both directions are offered. A requester may say
that their anchor is the parent, grandparent, aunt/uncle, spouse, sibling, or
cousin of the receiving anchor, or that their anchor is the biological,
gestational, donor-conceived, intended, adopted, foster, step, chosen,
community, or spiritual child, ward, grandchild, or niece/nephew of the
receiving anchor.

## Automatic placement

| Edge | Target generation relative to source |
| --- | ---: |
| Parent/guardian/caregiving parent -> child | +1 |
| Grandparent -> grandchild | +2 |
| Aunt/uncle -> niece/nephew | +1 |
| Partner, sibling, cousin, same-person bridge | 0 |
| Child -> parent (cross-household bridge choice) | -1 |
| Grandchild -> grandparent (cross-household bridge choice) | -2 |

Customers cannot type or lock a generation. The placement solver derives every
generation from relationship constraints, creates/updates one lineage node per
member, and rejects a relationship that would put one person in two different
generations or create an ancestry cycle. Isolated people in a multi-member
family remain visibly `unplaced` instead of being silently guessed into a row.

## Family Keys and household links

### Availability and authority

| Action | Who can do it | Package requirement |
| --- | --- | --- |
| Generate, view metadata for, or revoke a branch key | Billing owner or co-owner; authorized internal admin | `can_link_households` |
| Request a household link | Billing owner or co-owner | Both workspaces must have `can_link_households` and branch capacity |
| Accept/reject a link | Billing owner or co-owner of the receiving workspace | Receiving workspace must remain eligible |
| View the privacy-filtered linked network/reunion status | Authenticated workspace member with package access | Linked-household package for network traversal |

The raw Family Key is displayed once. Only its cryptographic hash is stored.
The key authorizes a handshake; it does not merge accounts, reveal passwords,
or transfer ownership. The durable link stores both household IDs, both
selected member anchors, the relationship direction, the generation delta,
and the computed household generation offset. Both active keys must still
match when the receiving owner accepts.

Key uses are reserved atomically against `max_uses`, so simultaneous requests
cannot silently overrun a one-use key. Revocation changes status and preserves
the audit evidence rather than deleting it.

Linked-tree and reunion views consume the same approved link graph. They apply
household offsets, flag alignment conflicts, and exclude an external living or
deceased person unless the owning household explicitly enabled cross-branch
sharing. External relationship facts require their own linked/branch/public
privacy scope. Portraits cross the boundary only when the portrait upload also
allows linked-family sharing.

## Portrait dropbox and automatic placement

1. The Portrait Upload page loads the selected family and creates one named
   dropbox for every family member.
2. The uploader chooses the image inside that person's box and must attest both
   lawful authority and the required living-person/guardian consent.
3. The backend validates file type/size, stores the file in that member's
   private family path, and records it as a pending submission. A pending file
   never replaces the active portrait.
4. Malware scanning runs against the actual stored path. Infected, failed, or
   unscanned files cannot be downloaded or approved.
5. A master account with `uploads.admin.review` reviews the portrait. Approval
   is impossible unless the scan is clean and both attestations exist.
6. Approval updates the member's active `approved_photo_upload_id`. Rejection
   does not remove a previously approved different portrait.
7. The normal tree and authorized linked tree resolve only a clean,
   non-quarantined, consent-attested, master-approved portrait.
8. The private cinematic manifest dynamically creates a slide for every
   approved member portrait. The slide carries the solved generation and
   relationship-aware parent, child, partner, and branch navigation. No manual
   slide copying is required.

The Evidence Review queue is separate. It lets the master account approve,
reject, or request correction for clean verification documents. Approved
documents may support the Verified Tree, but the documents themselves remain
private and never become NFT content.

## Family reunion command view

The Family Reunion page shows completion states for every person visible
through the authorized linked network:

- portrait: missing, pending scan, security blocked, consent missing, pending
  master review, rejected, or approved;
- placement: root, placed, or unplaced;
- account: not required, not claimed, or claimed;
- verification: not submitted, pending, or verified;
- automatic cinematic slide: ready or not ready.

It groups results by household and shows completion percentages. It does not
return passwords, MFA information, wallet secrets, private files, or the
unshared records of another household.

## Canonical people and duplicate prevention

Person matching is opt-in on both records. Same-household comparisons are
allowed; cross-household comparisons require an approved direct household
link. Exact birth year now contributes when a complete birth date is not
available. A match is a review candidate only—people are never merged
automatically. This protects the PDF's hardest rule: one real person may appear
in several household views but must not be silently duplicated or collapsed.

## Blockchain minting

The NFT is a public-safe continuity anchor, not the storage location for the
private tree or vault and not, by itself, a legal transfer of family ownership.
The configured token types support portrait, household, branch, and
organization anchors.

Minting is staged:

1. An internal mint operator prepares a versioned mint record and public-safe
   poster choice.
2. The internal operator records production approval.
3. The authenticated billing owner or co-owner records customer consent,
   public-title/poster choices, and the recipient wallet. An administrator is
   forbidden from fabricating this customer consent.
4. Policy, package, project state, public-content approval, fee, and readiness
   gates must all pass.
5. Idempotent jobs build the public manifest, generate the poster, submit the
   anchor transaction, and synchronize the receipt.
6. A signer lease serializes nonce use. The pending nonce is used, and the
   signed transaction hash and exact signed bytes are persisted **before**
   broadcast. A crash retries the same transaction rather than signing a second
   mint.
7. The receipt must succeed and emit an ERC-721 Transfer token ID. Tomb of Light
   then saves chain, contract, token ID, transaction hash, metadata URI, and
   public artifact hashes. Completed signed bytes are cleared.

An already canonical minted record is not reminted by client review, delivery,
maintenance, or this Phase 13 work.

## Remaining production closure work

These are explicit operational migrations or product decisions, not hidden
automatic behavior:

1. **Legacy reconciliation:** report and repair old manual generations,
   lineage-node gaps, unanchored household links, and old portrait approvals
   that lack the new consent attestations. Old files must not be grandfathered
   into public/cinematic display without evidence.
2. **Divorce, death, and succession:** the PDF specifies household split and
   owner -> co-owner/designated-heir transfer. Tomb of Light still needs a
   governed case workflow with both authorization and immutable evidence; it
   must not be implemented as a silent role edit or automatic NFT transfer.
3. **Invitation delivery and reminders:** a family member can now be marked as
   account-required with an expected email and viewer/contributor role, and
   reunion readiness matches that expectation to active project membership.
   Automated email/SMS delivery and reunion reminders still need their own
   consented communications design and provider integration.
4. **Production acceptance:** after merge/deploy, run a controlled smoke test
   with two non-production households, reciprocal keys, inverse generation
   placement, one clean portrait approval, one rejected portrait, one verified
   evidence record, reunion status, and a testnet mint. Do not test by reminting
   an existing customer's canonical NFT.

These remaining items should stay visible in operational readiness until their
workflow and migration evidence are complete.
