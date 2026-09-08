# Step 8.1 — Layered Customer Portal Architecture

This branch replaces the long customer dashboard stack with a layered customer application shell while preserving the secure routes and authorization model already in production.

## Home

Home is intentionally limited to:
- workspace/project identity
- one authoritative next action
- compact project progress
- no more than four quick actions
- maintenance or intake attention state

The prior detailed dashboard panels remain in the DOM temporarily for compatibility with existing secure controllers, but are not part of the ordinary customer Home experience. The governed Legacy Anchor can still be opened as a focused Deliverables subview without restoring the full legacy dashboard stack.

## Navigation domains

- Home
- My Project
- Family
- Uploads
- Vault
- Deliverables
- Account
- Support

Desktop-class layouts from 900px upward use a persistent left application rail, including the approximately 960px Safari viewport that exposed the live Step 8 problem. Smaller layouts use the existing secure mobile menu with the same domain model.

Project, Family, Deliverables, Account, and Support use a protected section-hub route. Uploads and Vault retain their existing purpose-built secure applications.

## Truth semantics

Step 8.1 separates customer-facing lifecycle state from package inclusion:
- approved intake moves the next action to production materials
- approved intake does not imply uploads or verification are complete
- a project-state API failure is shown as unavailable rather than false `Not started` / `Start Intake`
- maintenance read-only state makes Billing the primary action
- generic Link Key capability does not appear as household branch linking; Household Link Keys require `can_link_households=true`
- Viewer and Lineage Certificate distinguish `Pending production`, `Ready`, and `Not included`
- Legacy Anchor distinguishes minted/governed/unavailable status without exposing private Vault records
- governed package acquisition remains access without paid-order semantics

## Cache and delivery integrity

The Step 8.1 dashboard controller and Step 8.1 stylesheet use new cache identities so returning customers do not remain on the pre-redesign dashboard after deployment. The protected section hub uses the hardened Sep. 7 app/auth asset revisions and restrictive CSP.

## Verification target

Final certification requires:
1. compile + architecture + contract guardrails
2. focused Continuity runtime checks
3. full backend regression
4. dependency security audit
5. complete browser suite, including the real Legacy Plus contradiction shape
6. responsive checks at 390px, tablet/mobile breakpoints, 960px desktop class, and 1440px desktop
7. post-merge Pages deployment
8. authenticated production smoke using the real Legacy Plus account

## Safety boundary

This slice changes only customer presentation, navigation, read-only state interpretation, and browser/static contracts. It does not charge/refund Stripe, mutate production MongoDB, write/delete Vault records, mint blockchain assets, execute Continuity Kernel mutations, send customer email, or delete accounts.
