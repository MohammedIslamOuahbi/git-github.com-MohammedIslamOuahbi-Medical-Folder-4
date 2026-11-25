# Stage 5A closure and remaining synchronization plan

Date: 2026-10-14

## 5A closure

5A is closed only as the local, durable evaluation and capability-ordering
scope. It does not declare synchronization, proof transport, or business
application complete.

| Requirement | Evidence | Result |
|---|---|---|
| A: reject a delayed `supported` response after a destination downgrade | `backend/recovery_tests/check_http_proof_capabilities.py`; delayed response is interpreted after a committed empty destination capability and returns `negotiation_failed`; a fresh PostgreSQL session observes one row, version `0`, latest sequence | Passed previously; not rerun because the affected code did not change |
| B: commit ordering under the advisory lock | `backend/recovery_tests/check_proof_capability_ordering_b.py` on isolated `ibn_sina_cap_7d4ae3b9`, Alembic `20261008_23`; `pg_stat_activity` showed the second request waiting with `wait_event_type=Lock`, `wait_event=advisory`, and `pg_blocking_pids` pointing to the first request | Passed: old `accepted` sequence 1, new `unsupported` sequence 2, one durable row version 0 |
| C: concurrent updates | `backend/recovery_tests/check_proof_capability_ordering_c.py`; coordinated start, responses at previous+1 and previous+2, one final row matching the higher response | Passed previously; not rerun because the affected code did not change |

The general Alembic comparison still reports the documented
`users/user_permissions` schema debt. It was not changed or hidden. No demo
database was used for the B rerun, and no medical or incoming business rows
were applied.

## Current synchronization map

| Area | Current implementation | Status / remaining work |
|---|---|---|
| Durable local change registration | Protected worker/company/campaign paths reserve `LocalWriteOperation`, write `LocalRevision` and `SyncChange`, and use `X-Operation-UUID`; retry and guarded writes are implemented | Extend the same primitive to any remaining mutable entity before enabling its sync path |
| Transport, ACK, resume, deduplication | `SyncTransportWorker`, claim/lease delivery, HTTP receive/ACK, cursor/receipt persistence, revocation-aware reauthorization, and `resume_relay_delivery` exist | Full multi-peer HTTP completion and receive-before-ACK revocation policy remain separate evidence items; proof transport is negotiated but not sent |
| Received-event validation and proof | `SyncTransportEvent`/inbox validation, publisher scope, device authentication, and 5A proof evaluation ledger exist | Operational origin-proof issuance/verification and proof transport are intentionally blocked |
| Conflict discovery | `CentralSyncService._detect_conflict` records `SyncConflict` for signed records, workers/users/visits and field conflicts | Policy choices for medical conflict review and resolution must be approved before opening resolution |
| Atomic application/version protection | `receive_batch` and central import use nested transactions, UUID identity, version stamping and conflict buckets; central pull now shares `_application_conflict` for exact `base_version`, local-edit, and signed-record checks and skips an already journaled `change_uuid` | Incoming business application is still guarded; end-to-end entity tests remain blocked until proof eligibility and the guarded apply fixture are available |
| Device permissions/authentication | `require_sync_transport_device`, relay authorization scopes, publisher/device/generation checks and default deny are implemented | Revocation/regrant and foreign-scope HTTP matrices need continued isolated coverage |
| Full initialization and attachments | Recovery/bootstrap and attachment manifest/import primitives exist | End-to-end initialization with attachment integrity and resume is not proven as one supported workflow |
| Signed documents | Signature authorization and immutable signed/validated/printed document checks exist in certificate services | Cross-node preservation and conflict behavior for signed documents needs an approved policy and isolated tests |

### Transport completion evidence (2026-10-14)

`backend/recovery_tests/check_http_worker_receive_then_revoke.py` was run
against the isolated databases `ibn_sina_stage5a_0215a073` and
`ibn_sina_cap_7d4ae3b9`, both upgraded and verified at Alembic
`20261008_23`. A deterministic worker gate stopped after destination receive
committed and before source ACK. A new session observed one inbox row, one
canonical transport event, and one publisher-scoped receipt. Revocation then
caused HTTP 403/`SYNC_RELAY_NOT_AUTHORIZED`; the source delivery became
`rejected` with `RELAY_AUTHORIZATION_REVOKED`. After an authorized service
resume and a fresh worker process, ACK returned HTTP 200 and the delivery
became `delivered`. A fresh session verified one inbox, one receipt, one
delivery, and a cursor whose publisher event and sequence matched the receipt
(`last_publish_sequence=1`); publisher, origin, generation, clinic, and peer
scope all matched. Medical visit count remained zero.

This closes the receive-before-ACK/regrant evidence item only. It does not
enable proof transport, incoming business application, or clinical use.

## Ordered implementation plan

1. **Transport completion evidence ? closed 2026-10-14.** Reuse
   `sync_v2.py`, `sync_transport_service.py`, `sync_transport_worker.py`,
   `check_http_cycle.py`, and the publisher-scope fixtures. Add the missing
   receive-before-ACK/regrant and two-peer restart assertions. Acceptance:
   committed claim before HTTP, durable receive/ACK/cursor/receipt, safe
   retry, and no duplicate source or inbox row.

2. **Entity application contract ? next, decision-gated.** Reuse
   `central_sync_service.py`, `client_sync_import_service.py`,
   `sync_conflict.py`, and `local_revision.py`. Add per-entity atomic
   application tests with stale parent, local edit, duplicate, and rollback
   cases. Keep the stage guard closed until authorization evidence is present.
   Before implementation, product approval is required for worker and visit
   conflict outcomes; this task must not silently choose an auto-merge or
   last-write-wins policy.

3. **Origin-proof completion.** Reuse the 5A/P1/P2-A proof request, trust,
   revocation, time, and verification services. Implement issuance only after
   the trust/time policy and transport negotiation are accepted; verify
   binding, delegation, revocation ordering, and replay without changing the
   event fingerprint.

4. **Attachments and signed-document policy.** Reuse document storage,
   attachment manifests, signature authorization, and immutable status checks.
   Add hash-preserving transfer and conflict tests before any business apply.

5. **Controlled application pilot.** Only after the preceding evidence and
   policy decisions, enable a small workers-only application path with audit,
   rollback, and explicit authorization. Visits and signed medical documents
   remain review-gated.

## Decisions requiring product approval

The policy supplied on 2026-10-14 is accepted as the contract input for the
next test task: automatic application is permitted only when `base_version`
matches the local version and no pending local edit exists; conflicts retain
both versions; signed documents are never overwritten; ACK remains transport
only. This acceptance does not open the application guard.

- Whether a worker conflict may be auto-applied when origin proof and version
  checks are valid, or must always be reviewed.
- Whether a visit conflict is reviewed by a physician in the receiving clinic.
- Whether signed documents are immutable across replicas and what happens when
  a signed record conflicts with an unsigned local edit.
- Which trusted authority supplies offline time evidence and how uncertain
  revocation ordering is handled.

### Entity application contract progress (2026-10-14)

`central_sync_service.py` now uses one `_application_conflict` preflight for
central-pull application. It requires exact `base_version` equality when an
existing entity is present, delegates local-edit/signed-record/visit checks to
`_detect_conflict`, records a pending `SyncConflict` instead of issuing an
`ON CONFLICT DO UPDATE`, and skips an already journaled `change_uuid`. This
prevents an upsert from bypassing the policy. `py_compile` passed.

The guarded `central_pull_apply` path still fails closed with
`OPERATION_SUSPENDED_FOR_DATA_SAFETY`; no business rows were written in the
current demo or in this change. Full isolated apply assertions (clean worker,
local edit, visit review, signed document, and rollback) are the next test
item once an approved proof-eligible fixture is available. No automatic
application has been enabled.

## 5A application-eligibility audit (2026-10-14)

The receive path is transport-only. `SyncTransportService.receive` authenticates the
device and relay scope, persists `SyncEventInbox` and the delivery/receipt state, and
ACK/delivered only report transport progress. There is no production path that turns
those states into application eligibility. `central_sync_service.apply_central_pull`
and `client_sync_import_service.import_package` both call
`suspend_for_data_safety(...)` before any business-row write. Consequently the
external path is still 423-blocked, and `snapshot_new_row` cannot bypass the guard:
its `ON CONFLICT` branch is reached only after that guard (and is additionally
rejected with `SYNC_APPLICATION_CONTRACT_REQUIRED` for an existing syncable row).

The existing internal entity-contract checks remain explicitly internal. They cover
base-version equality, pending local edits, duplicate `change_uuid`, signed-record
immutability, visit review classification, conflict snapshots, and rollback. They do
not prove end-to-end application of a visit or signed document.

### Rejection evidence

Executed on isolated `ibn_sina_stage5a_0215a073` (Alembic `20261008_23`) with
`backend/recovery_tests/check_application_eligibility_rejections.py`:

| condition | observed result |
|---|---|
| missing proof fields | `invalid` / blocked |
| event/content mismatch | `binding mismatch` / blocked |
| clinic/service/device scope mismatch | `mismatch` / blocked |
| revoked transport device | `SYNC_DEVICE_NOT_AUTHORIZED` |
| business-side effect | `business_tables_changed=0` |

No proof was issued, no application guard was opened, and no demo database was used.

### Missing dependency and next task

The missing dependency is a reviewed, durable eligibility gate joining an inbox event
to a current `ProofVerificationResult` (signature, binding, trusted-key scope,
delegation scope, revocation/time state, and policy fingerprint). An accepted proof
cannot be manufactured by this test: issuance and proof transport/negotiation must
first deliver a verifiable proof and preserve its immutable binding. The smallest
next task is therefore to specify and implement that pure gate plus rejection tests
(`proof missing`, `invalid`, `scope mismatch`, `revoked device`, `content mismatch`)
behind the existing safety barrier; opening `central_pull_apply` remains a separate
decision after those proofs exist. No automatic visit or signed-document application
is claimed.

The contract runner was extended and rerun on the same isolated head. It now
also proves duplicate `change_uuid` detection, signed-record update and delete
classification as immutable, validated-visit classification as physician
review, durable local/incoming snapshots with base and central versions and
event identity, snapshot-update rejection with
`SYNC_APPLICATION_CONTRACT_REQUIRED`, and that a new snapshot row is only a
fixture/import shape and not an application authorization. The external apply
guard still rejected the call and no business application occurred.

The isolated contract runner `backend/recovery_tests/check_entity_application_contract.py`
was executed on `ibn_sina_stage5a_0215a073` at head `20261008_23`. It proved
matching base/no local edit yields no conflict, a mismatched base yields
`base_version_mismatch`, a pending local edit yields `local_edit_pending`, the
local value survives rollback, and the external `central_pull_apply` path is
still rejected by `OPERATION_SUSPENDED_FOR_DATA_SAFETY`. This is internal
policy evidence only; no business event became eligible or applied.

`client_sync_import_service.py` now refuses an existing syncable row without
the event application contract (`SYNC_APPLICATION_CONTRACT_REQUIRED`) before
its snapshot upsert. This prevents its `ON CONFLICT` path from bypassing
version, local-edit, or signed-record checks. Full signed-document and visit
application remains unexecuted because the guarded application path is still
closed.

No barrier is opened by this document. Tauri, proof issuance/transport, and
incoming medical application remain out of scope.
### Shared eligibility gate (2026-10-14)

Added `app/services/application_eligibility_service.py`. Its pure
`evaluate_application_eligibility` function requires current event identity,
content hash, clinic/service/device scope, and a persisted
`ProofVerificationResult` whose signature, binding, key trust, delegation, and
time results are all valid. Missing or stale evidence returns a specific blocked
reason; client-supplied `verified` or `eligible` flags are ignored. The existing
`proof_verification_service.save_verification_result` and
`sync_application_evaluation_service.evaluate_event` remain the persistence
services for attempts, fingerprints, evidence references, and the current
decision; no parallel verification ledger was introduced.

Isolated `check_application_eligibility_gate.py` passed missing proof, content
change, scope change, revoked delegation, expiry, and revocation-fingerprint
change/re-evaluation checks. This is a gate/unit result only: no proof was issued
or transported, and no business application path was opened. A future apply
transaction must re-read the current fingerprint and gate result under its own
transaction; a saved decision is not permanent authorization.

### Proof issuance dependency (2026-10-14)

The requested local issuance run is intentionally blocked at the dependency
boundary. The repository contains `proof_verification_service` and the trusted
key/delegation/revocation models, but no production issuance service or approved
private-key manager. Existing P2-A scripts generate ephemeral Ed25519 keys and
sign fixture dictionaries directly; those are verification fixtures, not an
issuance path and are not promoted to operational trust. Therefore no
`ProofVerificationResult=eligible` was fabricated, no proof was issued or
transported, and no business table was written.

To proceed, the next bounded task must first define the approved issuer contract:
private-key custody, authority registration, immutable proof envelope, and the
atomic link to `OriginProofRequest`. Its acceptance tests must then exercise the
issuer, `verify_signature`/binding/scope/time/revocation, and the eligibility
gate on an isolated database. Until that service and key custody are approved,
the gate remains rejection-only and the application guards stay closed.
### Isolated proof issuer (2026-10-14)

Added migration `20261008_24` and the `OriginProof` model to persist the
immutable proof envelope linked one-to-one with `OriginProofRequest`. Added
`ProofIssuerService` with a `KeyProvider` interface and a memory-only
`MemoryKeyProvider`; it is test-only and does not persist private keys or expose
an endpoint. The issuer reads `SyncChange`, checks trusted key scope and active,
unexpired delegation, signs the existing deterministic envelope, and writes the
proof/request update in the caller's transaction. Matching retries return the
same proof; request/event or content mismatch and signing failures are rejected.

`check_local_proof_issuer.py` ran on isolated `ibn_sina_stage5a_0215a073` at
Alembic `20261008_24` and passed real Ed25519 signing, verifier signature and
binding checks, key/delegation scope, eligibility gate acceptance in test-only
memory, idempotent retry, content/signature mutation, revoked key/delegation,
expiry, and fresh-session persistence. No business row, transport record, or
production key was created. The memory provider is not production key custody;
an approved HSM/keystore provider and proof transport remain required.
### Proof issuer failure/concurrency coverage (2026-10-14)

`check_local_proof_issuer.py` now covers the remaining issuer cases on isolated
Alembic `20261008_24`: request identity/content reuse is rejected without a new
proof; missing `KeyProvider` material fails before completion; an injected
post-insert failure rolls back the proof and request status; and two independent
transactions for one request converge through the row lock and database unique
constraints to one proof and one binding identity. The successful path uses real
Ed25519 signing and the existing verifier. `check_stage5a_p2a.py` was rerun after
the delegation state/expiry change and passed.

The next bounded task is the `OriginProof` transport contract: capability
negotiation, immutable envelope transfer, receipt/ACK semantics, and replay-safe
resume. It must not change event fingerprints or open business application.
### OriginProof transport readiness review (2026-10-14)

The current HTTP transport exposes capability negotiation plus `/sync/v2/pull`,
`/receive`, and `/ack`; it has no authenticated OriginProof receive/store/ACK
route and no worker sender branch for an immutable proof envelope. The worker's
negotiator only decides whether a future proof send is allowed; it does not send
proofs. Therefore a real supported HTTP proof-transfer run cannot be claimed
without creating a second protocol, which is explicitly out of scope.

The existing `OriginProof` issuer and verifier remain local-only. The next task
must define and implement the missing authenticated endpoint and durable
publisher-scoped proof receipt/link table using the existing device, relay,
capability, and ACK primitives. Required acceptance cases are supported transfer,
unsupported/failed negotiation with no send, immutable replay, receive-before-ACK
restart, revoked authorization, proof-before-event ordering, and verifier-only
processing. No transport was opened in this review and business application stays
guarded.
### OriginProof transport skeleton (2026-10-14)

Added migration `20261008_25`, `OriginProofTransportReceipt`, and authenticated
`/sync/v2/proof-receive` and `/sync/v2/proof-ack` routes. They reuse device and
relay authorization, validate the existing proof envelope binding, reject content
changes under the same proof identity, and keep receipt/ACK separate from
verification and application. The routes are disabled unless the process-local
test setting `PROOF_TRANSPORT_ENABLED=1` is explicitly supplied; the default
runtime remains closed.

Migration and Python compilation passed on isolated
`ibn_sina_stage5a_0215a073` at `20261008_25`. Full HTTP/worker proof transfer,
resume after receive-before-ACK, and proof-before-event reconciliation are not
claimed yet: `SyncTransportWorker` still has no proof sender branch. The next
change must add that branch using the existing capability negotiator, with
unsupported/failed negotiation preventing proof sends while leaving event
transport unchanged.
### Proof sender hook (2026-10-14)

`SyncTransportWorker` now accepts an optional `proof_sender`. It is invoked only
after the existing negotiator returns `supported`; unsupported or failed
negotiation never calls it, and the event sender/ACK path remains independent.
The hook is process-local and intentionally requires the test runner to provide
the authenticated HTTP sender.

The requested full independent-process cycle is not yet evidenced: durable
source-side proof delivery claims/retries and a worker runner that supplies the
authenticated proof sender are still missing. Therefore no supported proof
transfer is declared complete. Proof-before-event and interruption/resume remain
the next items after the basic cycle is wired and tested.

- Proof-before-event: implemented isolated reconciliation helper and HTTP test for proof-before-event then matching event; business application remains blocked. Mismatch/restart/revocation variants remain pending.

- Time/revocation review: check_local_proof_issuer.py uses synthetic SimpleNamespace time_valid for unit eligibility only; it is not operational time evidence. Reconciliation now returns time_indeterminate and revocation_order_indeterminate without trusted evidence, and remains blocked. origin_service_uuid is a signed contract field; old proofs without it remain unsupported for full verification.

- Time evidence contract revised: independent from revocation/checkpoints; sequence starts at 1 per chain_scope, accepts only initial/next, duplicate matching is idempotent, gaps/out-of-order/conflicting fingerprints remain blocked. No time_valid or application eligibility is granted by storage validation.

- Freshness evaluator separated signature/binding, RTT freshness, conservative time interval, and authority trust. Test-only acceptance requires explicit test-time-authority policy; production authority remains untrusted and application blocked. Interval = authority_issued_at +/- (authority_uncertainty + RTT/2).

### Revocation chain coverage (2026-10-15)

Migration `20261008_30` adds the immutable `proof_revocation_chain_records` envelope.
Records are signed with canonicalization `revocation-chain-deterministic-json-v1`
and domain `medical-folder/revocation-chain/v1`; the fixed genesis anchor is 64
zeroes and is not client-selectable. Identity is authority + chain scope +
contract version + sequence. Out-of-order storage is allowed, while coverage
returns `complete`, `incomplete`, or `conflicting` and never implies freshness or
application eligibility. Legacy ProofRevocation rows are not retroactively
covered.

`check_revocation_chain_coverage.py` ran on isolated
`ibn_sina_cap_7d4ae3b9` after upgrade to `20261008_30`, covering complete and
gap-then-fill chains, out-of-order insertion, invalid signature, sequence
conflict, checkpoint-head mismatch, idempotent replay, and transactional
rollback. Checkpoint freshness and full revocation checkpoint reconciliation
remain separate work.

### Integrated revocation checkpoint freshness test (2026-10-15)

`check_revocation_checkpoint_integrated.py` exercised a one-use destination
challenge, a signed checkpoint bound to destination, chain scope, policy, and
chain head, independent chain coverage, and the existing monotonic freshness
evaluator. The isolated test accepted only the complete/current test-authority
case. It rejected delayed responses, replay, challenge/destination/policy
mismatches, and a recent response whose chain was incomplete. The accepted result
is explicitly `time_valid_test_only`; it does not grant operational trust,
application eligibility, or freshness across process restart.

### Evidence gate binding (2026-10-15)

`origin_proof_reconciliation.reconcile_origin_proof` now accepts an explicit
isolated-test evidence bundle and verifies checkpoint challenge, destination,
chain scope, covered sequence, covered chain hash, complete chain coverage, and
test-only freshness before returning `accepted_test_only`. Missing or mismatched
evidence remains rejected; production callers that omit the bundle remain
blocked. The result includes an evidence fingerprint and `business_application=0`.
Automatic HTTP receive wiring and durable persisted verifier-result references
remain pending because the current proof-receive contract does not carry the
checkpoint/freshness evidence bundle.

### Local proof trust binding (2026-10-15)

Migration `20261008_31` adds `proof_trust_bindings`. Bindings are local trust
administration records and are never created by proof-receive. The resolver
requires signing key, issuer, clinic, service, and policy agreement; missing,
ambiguous, or revoked bindings return blocked. Each binding has a versioned
input fingerprint, so changing state or version prevents reuse of prior
verification results. The binding selects revocation authority and chain scope
only; checkpoint selection, coverage, and freshness remain delegated to their
existing services.

### Durable reconciliation queue (2026-10-15)

Migration `20261008_32` adds `origin_proof_reconciliation_tasks` with logical
deduplication, attempts, availability, lease ownership, and retry state.
Proof receive schedules a task only after resolving a local trust binding and
within the same database transaction; evaluation is performed after commit in a
new session. Claims use row locking and expired leases are recoverable.
Checkpoint selection is restricted to the binding authority/scope/contract/policy,
verifies checkpoint signatures, and requires complete chain coverage; it never
uses latest arrival as evidence and does not establish freshness.

### Automatic reconciliation evidence gate (2026-10-15)

The isolated head-32 HTTP run completed the durable task after checkpoint
signature/coverage and test-authority freshness passed.  A new PostgreSQL
session confirmed `origin_proof_reconciliation_tasks.state=completed` and a
stable application-attempt fingerprint.  The shared application evaluator
(`sync_application_evaluation_service.evaluate_event`) deliberately returns
`blocked_authorization_evidence`: its required input is trusted operational
authorization evidence for the medical operation, not device transport
authorization or proof-signing delegation.  The fixture's checkpoint and
freshness authority are test-only evidence and are never promoted to that
input.  Consequently `eligible` and `applied` remain absent and
`business_application=0`; no business table is written.

The next smallest task is to define and implement the operational
authorization-evidence contract and its verifier (including issuer, scope,
validity/revocation, and audit references), then test its rejection paths in an
isolated database.  Acceptance requires a trusted evidence record consumed by
`evaluate_event`, persisted decision/attempt fingerprints, and unchanged
business tables.  This must not open the application gate until its policy and
tests are approved.

### Authorization evidence contract (2026-10-15)

The current contract requires a signed, trusted evidence record bound to
`subject_user_uuid`, `operation_uuid`, `event_uuid`, entity type/UUID,
content hash, clinic/scope, policy version, issuer, and evidence identity.
`LocalWriteOperation` records the local actor and operation UUID, while
`OriginProofRequest` records the proof request's actor, operation, event,
content, clinic, entity, and policy fields. Transport relay authorization and
proof-signing delegation authenticate transport/provenance; neither proves the
user's authority to perform the medical operation. A later application check
must also remain distinct from the authority held when the original operation
was executed; later revocation does not silently rewrite that historical fact,
and unproven device time/order cannot establish it.

`classify_authorization_evidence` currently rejects missing, incomplete,
mismatched, and issuer-unverified evidence. This is intentional: no trusted
operational issuer/verifier has been approved, so even a role string or a
signature-shaped value remains blocked. The focused rejection matrix is
`recovery_tests/check_authorization_evidence_rejections.py`; it never writes
business data or grants `eligible`.

### Isolated authorization evidence issuer/verifier (2026-10-15)

`authorization_evidence_service.py` now provides a versioned, domain-separated
Ed25519 envelope for isolated tests. The issuer scope is explicit and must
match the clinic/entity/operation scope; the issuer is separate from the
OriginProof signing key. Issuance receives the trusted record values as
arguments and signs canonical bytes; it does not accept a client role or
permission flag. Verification independently checks issuer identity/scope,
all event/user/operation/entity/content/clinic/policy bindings, and the real
signature. Successful verification is named `accepted_test_only` only.

`check_authorization_evidence_issue_verify.py` exercises authorized issuance,
user/operation/entity/content/scope/issuer/policy mismatches, tampered
signatures, and the evidence fingerprint. It performs no database or business
write. A production issuer still requires a historical authorization record
captured at local execution time and an approved trust registry; until then
`evaluate_event` remains `blocked_authorization_evidence`, independently of
transport authorization, proof delegation, and time freshness.

`issue_for_local_operation` now calls the existing `permission_service` and
binds issued evidence to the durable `LocalWriteOperation` actor and content.
Matching retries return the stored evidence; content changes or actor
mismatches are rejected, and permission failure occurs before evidence is
written. The focused operation test covers idempotency, conflicts,
unauthorized issuance, and the zero-business-write invariant. Its permission
adapter is test-only; an end-to-end database run with real user rows remains
the next verification task before any production issuer is trusted.
