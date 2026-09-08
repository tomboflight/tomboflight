# Step 8.1 — Layered Customer Portal Architecture

This branch replaces the long customer dashboard stack with a layered customer application shell while preserving the secure routes and authorization model already in production.

## Home

Home is intentionally limited to:
- workspace/project identity
- one authoritative next action
- compact project progress
- no more than four quick actions
- maintenance or intake attention state

The prior detailed dashboard panels remain in the DOM temporarily for compatibility with existing secure controllers, but are not part of the customer Home experience. Dedicated routes own their respective functions.

## Navigation domains

- Home
- My Project
- Family
- Uploads
- Vault
- Deliverables
- Account
- Support

Desktop uses a persistent left rail. Smaller layouts use the existing secure mobile menu with the same domain model.

## Truth semantics

Step 8.1 separates customer-facing state from entitlement inclusion:
- approved intake moves the next action to production materials
- approved intake does not imply uploads or verification are complete
- maintenance read-only state makes Billing the primary action
- generic Link Key capability does not appear as household branch linking
- granted package acquisition remains access without paid-order semantics

## Safety boundary

This slice changes only customer presentation, navigation, and browser/static contracts. It does not charge/refund Stripe, mutate production MongoDB, write/delete Vault records, mint blockchain assets, execute Continuity Kernel mutations, send customer email, or delete accounts.
