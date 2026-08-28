# Private Bridge Event Secure Access Runbook

Date: 2026-08-28

Owner: canonical CEO / Super Admin

## Security boundary

Private Event 2 promotion values are backend runtime secrets. They must not be placed in HTML, JavaScript, MongoDB invitation records, API responses, audit payloads, tickets, screenshots, chat, or Git history.

The customer flow is:

1. The CEO selects one invited email address and one eligible package in `admin-event-access.html`.
2. The backend stores only an HMAC hash of a high-entropy, one-time access token.
3. Postmark sends the token as a URL fragment so it is not included in normal HTTP request or referrer logs.
4. The guest enters the exact invited email address.
5. The backend atomically consumes the token and sends only that package's private promotion value to the invited mailbox.
6. The promotion value is never returned to the browser or stored in the invitation record.

The public claim endpoint is recipient- and IP-rate-limited, returns the same generic response for valid and invalid claims, and sends `Cache-Control: no-store`.

## Required rotation before deployment

Values previously committed to public source must be treated as compromised even after removal. Do not reuse or rename them.

1. In Stripe, deactivate every previously published Event 2 promotion code.
2. Confirm each retired value can no longer be applied at checkout.
3. Create one new promotion code for each canonical package. Each Stripe promotion must:
   - apply only to its intended one-time package product;
   - provide the approved 50% Event 2 discount;
   - exclude maintenance, subscriptions, add-ons, services, taxes, and future balances;
   - expire at the approved Event 2 deadline;
   - use the approved redemption limit.
4. Place the new mapping only in Render's protected environment variable `BRIDGE_PAINT_PROMOTION_CODES_JSON` using these keys:

```json
{
  "legacy_snapshot": "<new Stripe value>",
  "legacy_portrait_intro": "<new Stripe value>",
  "digital_legacy_portrait": "<new Stripe value>",
  "household_foundation": "<new Stripe value>",
  "heirloom_legacy_tree": "<new Stripe value>",
  "legacy_plus": "<new Stripe value>",
  "family_estate_concierge": "<new Stripe value>",
  "command_structure_network": "<new Stripe value>"
}
```

5. Set `BRIDGE_PAINT_EVENT_EXPIRES_AT` to the approved UTC deadline and keep `BRIDGE_PAINT_ACCESS_RATE_LIMIT` at or below the reviewed value.
6. Redeploy the backend. Do not place real values in `.env.example` or any local file that can be committed.

## Verification gate

Before issuing an invitation:

1. Sign in as the canonical CEO.
2. Open `admin-event-access.html`.
3. Confirm **Protected configuration** reports all eight packages ready and shows the correct expiration.
4. Issue a test invitation to a controlled mailbox and select one package.
5. Confirm the invitation link contains the token after `#invite=` and that the browser removes it from the address bar after loading.
6. Confirm the public page never displays or returns a promotion value.
7. Confirm the private offer email reaches only the invited mailbox.
8. Confirm the invitation history changes to `fulfilled` and the same link cannot deliver again.
9. Confirm audit evidence exists for invitation delivery and promotion delivery.

## Incident response

If a replacement value is exposed, deactivate it in Stripe first. Then remove it from the protected environment, create a new value, update Render, redeploy, revoke affected pending invitations, and issue new invitations. Source removal alone is not remediation because public history and caches may retain the former value.
