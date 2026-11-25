# Head 20261008_36 integration status

## Worker create/update test scope

The isolated Worker checks now cover a real protected local create and update,
durable journal events, historical authorization capture, signed OriginProof,
HTTP receive, reconciliation, test-only internal application, replay
idempotency, pending-local-edit conflicts, and rollback paths. The update
conflict run preserves the local edit and records one `SyncConflict`; replay
does not create another conflict or revision. These runs are test-only:
`business_tables_changed_in_test=1`, while
`production_application_enabled=0`, `eligible_production=0`, and
`production_applied=0`. The create/update source fixture and the HTTP runs are
reported separately; only the latter exercised transport and reconciliation.

## MedicalVisit source fixture

`recovery_tests/check_medical_visit_source_fixture.py` is the next smallest
source-only step. It uses `MedicalVisitService.create` with an authenticated
test user and an existing worker dependency, sets the journal source context,
and verifies in a fresh PostgreSQL session that one visit and one journal
`SyncChange` exist with matching user/source identity, operation, entity, hash,
and captured `medical_visits.create` authorization decision. Repeating the same
operation UUID returns the same visit and leaves one event.

No HTTP receive, incoming application, medical-document signing, production
eligibility, or Tauri path is exercised by this fixture.

The fixture now also issues and verifies a real Ed25519 authorization evidence
envelope and OriginProof for that same `medical_visits` insert event. Their
delegation is scoped to `medical_visits/insert`, and the worker reference in the
visit payload is carried as a stable UUID before hashing. Fresh-session checks
confirm one event, durable evidence/proof identities, and stable replay.

The internal primitive `apply_medical_visit_entity` is also covered by a
focused source-side check for replay, missing-worker rejection, and cleanup of
`sync_apply_mode`. A fresh target-side create/flush-failure run remains
pending; this round deliberately did not perform incoming application or
cross-database dependency preparation.

The `medical_visit_create` runner branch now uses the real visit event and
proofs with the existing relay, HTTP, reconciliation, checkpoint, and
freshness path. It applies the visit only through the isolated internal
primitive after reconciliation; authorization evidence is prepared locally and
is explicitly not a network-transport test. The run completed with one visit,
one revision, replay without duplication, and no incoming `SyncChange`.

The internal update check now applies the real `medical_visits.update` event
against a version-1 target snapshot with the signed parent revision, reaches
version 2 once, and replays without another revision or local journal event.

`prepare_medical_visit_update_source` now exercises the protected update path:
`base_version=1`, `entity_version=2`, and a durable parent revision. It captures
`medical_visits.update`, preserves the operation result, emits source identity
and content hash fields, and issues update-scoped authorization evidence and
OriginProof for the same journal event. The source-only run verified signatures,
bindings, persistence, and replay without another event or proof.

The update application check also covers independent base-version conflict
(`physician_review`, replay-deduplicated) and post-flush rollback followed by a
single successful retry. A medical signature-protection case remains separate;
the current run does not claim to exercise the full clinical signing workflow.

That target-side check is now implemented in
`check_medical_visit_application_internal.py`: the source event is prepared by
the real fixture, the worker dependency is resolved by UUID on the target,
visit application is atomic, replay is idempotent, and injected post-flush
failure rolls back the visit, revision, and processing record. It remains an
internal test only; no HTTP transport or production application path is opened.

## MedicalVisit `keep_local` closure and `accept_incoming` contract (design only)

The isolated `keep_local` matrix is closed.  It covers an authorized doctor,
permission denial, non-doctor eligibility denial, a changed local version, and
an injected failure after the conflict and audit rows are staged.  Fresh-session
checks show that rejected or rolled-back decisions leave `physician_review`,
empty resolution fields, unchanged visit/evidence data, and no partial audit;
the successful path is idempotent and does not emit an incoming `SyncChange`.

There is currently no executable `accept_incoming` option in the protected
MedicalVisit resolver.  `CentralSyncService.resolve_conflict` accepts the
keyword `resolution_type`; `keep_local` is the only MedicalVisit resolution
implemented there.  The legacy HTTP route (`POST /sync/resolve-conflict`) uses
`SyncResolveConflictRequest.resolution` values `server_wins`, `client_wins`,
and `merge`, but `SyncService.resolve_conflict` deliberately suspends this
legacy path.  It must not be used as an implementation of incoming acceptance.

The proposed option is therefore `resolution_type="accept_incoming"`, exposed
only through the protected internal resolver after the checks below.  It must
reload the conflict, OriginProof, authorization evidence, checkpoint/freshness,
UUID dependencies, and current local revision under a row lock; recompute the
input fingerprint; and reject stale evidence, changed versions, missing
dependencies, or revoked authority.  A prior reconciliation result is an
input, never an authorization to write.

Acceptance must preserve both branches: retain the local snapshot and incoming
event/proof references in an immutable conflict history, create a new
`LocalRevision` whose parent is the current revision, and record the physician's
decision and reason in an audit row.  The incoming event must not be re-emitted
as a new local `SyncChange`; a processing marker keyed by incoming
`event_uuid`/`operation_uuid` makes retries idempotent.  A changed local version
between review and commit rejects the decision without writes.  Applying to a
validated visit remains forbidden by the existing `validated`/`validated_at`
guard; document validation is a separate workflow and is not opened by this
contract.

### Fixed contract (non-validated MedicalVisit)

The option is fixed as `resolution_type="accept_incoming"` for the isolated
internal runner (not an HTTP or production route). It requires a
medically eligible doctor with `sync.resolve_conflicts` and a non-empty
`resolution_reason`. The resolver reloads OriginProof, authorization evidence,
dependencies, policy/trust versions, and the current local revision under a
row lock, recomputes the input fingerprint, and rejects stale data or a
validated visit without writes.

The current schema has only one revision parent. The incoming branch is
`SyncConflict.incoming_change_uuid` → `SyncChange.revision_uuid` (and its
`parent_revision_uuid`); the local branch is the latest
`LocalRevision.revision_uuid`, with `central_version` and `central_snapshot`
captured on the conflict. A decision revision must use
`kind="conflict_accept_incoming"` and parent the locked local revision. Its
second parent cannot be reduced to a number: a dedicated immutable decision
record (or versioned `SyncConflict` extension) must store incoming revision,
local parent, decision revision, both snapshots/hashes, doctor, reason,
evidence references, fingerprint, and policy/trust versions.

Entity update, decision record, conflict fields, and audit are one transaction.
Incoming content emits no local echo `SyncChange`. If decision distribution is
later enabled, it needs a separate decision event with a new operation UUID,
references to both revisions and the conflict, and deduplication by decision
UUID; no current service publishes this event, so echo suppression is not a
distribution contract.

The immutable `sync_conflict_decisions` record and migration `20261008_37`
now provide the two-branch references and decision revision identity. The
internal method is intentionally limited to the test runner; evidence and
freshness wiring remains a prerequisite before it can be considered a complete
acceptance path.

Acceptance tests: valid doctor/reason and non-validated visit; missing or
invalid evidence; stale version; validated-visit rejection; identical replay
without another revision/audit; different reason rejection; injected rollback
with no partial rows; preservation of both branch references and proofs; and
zero incoming echo changes. Production eligibility/application remains closed.
