# Continuity Kernel Phase 14 — Private Upload Storage Closure

Date: 2026-08-24

## Outcome

Phase 14 makes the private-upload pipeline use Render's persistent disk only for
staging and quarantine. A file must receive a clean malware verdict before it is
streamed into the dedicated private Cloudflare R2 bucket. The database becomes
authoritative for the R2 object only after that object write succeeds, and the
local staging copy is then removed.

The engineering verification in this phase does not upload, download, migrate,
or delete production customer files.

## Governed storage states

| State | Local disk | Private R2 | Download allowed |
| --- | --- | --- | --- |
| Pending scan | Staging copy | No object | No |
| Malware clean, promotion complete | Removed after promotion | Private object | Yes, after normal authorization |
| Malware detected | Quarantine copy | No object | No |
| Scanner or R2 error | Quarantine copy when possible | No newly authoritative object | No |
| Deletion pending or failed | Cleanup may be pending | Deletion unconfirmed | No |

Development environments without R2 may retain clean files locally. Production
never treats that fallback as successful: missing or failed private object
storage moves the upload into the blocked/quarantine path.

## Object confidentiality

- Private objects use keys rooted at `private-uploads/v1/` and contain system
  identifiers plus the generated stored filename, not the customer's original
  filename.
- The dedicated `R2_PRIVATE_BUCKET` setting is mandatory; the system will not
  silently place customer files in a generic metadata or poster bucket.
- Uploads set `Cache-Control: private, no-store`.
- Downloads require the existing workspace and privacy authorization checks,
  then redirect to a signed R2 URL with a two-minute lifetime.
- An explicitly selected approved NFT poster is read from private R2 through a
  bounded server-side path. If that approved source is unavailable, manifest
  preparation fails closed instead of silently minting an abstract substitute.
- Public serialization does not expose the staging path, R2 bucket, or R2 key.
- Infected, skipped, errored, quarantined, deletion-pending, and deletion-failed
  records cannot produce a download.

## Failure and deletion behavior

- If an R2 write fails, production keeps the file blocked and moves the staging
  copy into quarantine when possible.
- If the R2 write succeeds but the database authority update fails, the new R2
  object is deleted best-effort before the upload is quarantined.
- Deletion first validates every local path, marks the record pending, and then
  requests idempotent R2 deletion.
- If R2 deletion fails, the database record is retained with a failed status so
  the operation can be retried and audited; downloads remain blocked.
- Confirmed deletions also remove any residual staging file and the actual
  quarantine file, closing the earlier quarantine-orphan defect.
- Deleting an active or pending portrait clears its member-level pending,
  approved, and active-photo references before the upload record is removed.

## Protected readiness

Public liveness remains low-latency and does not disclose control details. The
CEO-only operational readiness surface now performs live, minimized checks for:

1. a writable Render disk mounted for staging and quarantine;
2. a configured and reachable scanner health check;
3. a configured and reachable dedicated private R2 bucket.

The protected gate also fails closed if it cannot count legacy clean local
uploads; an unknown migration inventory is not treated as zero.

Provider errors are reduced to control-state codes and exception types. Endpoint
URLs, bucket names, access-key identifiers, and secrets are not included in the
readiness response.

## Deployment boundary

New uploads begin using this lifecycle only after Phase 14 is merged and its
backend deployment is live. Existing clean local records are not silently moved
by engineering tests or application startup. Any legacy-file migration must be
counted first, verified against actual disk availability, and executed through a
separate governed, resumable operation that preserves authorization and evidence.
