# Stage-four final verification addendum

After the initial transport migrations, `20261008_02_add_event_clinic_identity.py` and `20261008_03_add_transport_leases.py` were applied only to the verified isolated PostgreSQL database `ibn_sina_recovery_test`. The final Alembic head is `20261008_03`. The latter adds a 30-second delivery lease and fencing token; an expired worker cannot acknowledge a claim taken by a newer worker. No clinic database was touched.

The transport integration test was rerun after this migration and passed. Scoped cleanup left zero rows in transport, recovery, evidence, and synthetic business tables.

The final transport test also passed durable exponential retry scheduling for temporary failures; permanent failures remain rejected and non-retryable. The HTTP router now exposes authenticated `/sync/v2/pull`, `/sync/v2/receive`, and `/sync/v2/ack`; the background worker claims and acknowledges outside the network transaction. The existing PostgreSQL test script proves direct receive and lease persistence, but a two-database HTTP A→B→C run and Windows multi-process lifecycle remain unverified. Final read-only identity was `ibn_sina_recovery_test` / `public` / 5432 with zero rows in all scoped synthetic tables.

The medical tables are not written by receive or the worker. Stage-one barriers remain active, and legacy central push remains suspended. This is transport preparation only; stage five is still required before any inbox event can be applied.

## Publication log implementation

Migration `20261008_04_add_publication_log.py` adds `sync_publication_counters` and `sync_event_publications`. `SyncTransportService.publish_committed()` selects only committed `SyncChange` rows, locks the per-source/generation/channel counter, allocates the next publication position, and commits the publication row and counter together. A unique constraint prevents duplicate publication of one event in a channel. `publication_batch()` reads these positions rather than `SyncChange.id`, and returns a cursor only from rows actually present in the returned batch.

The PostgreSQL acceptance script `recovery_tests/check_postgres_publication_log.py` passed: bounded batches, cursor continuation, idempotent repeated publishers, and scoped cleanup. The existing transport, stage-three, and barrier tests also passed after the head moved to `20261008_04`. Because publication is selected only after commit, a transaction that commits later receives a later publication position; no network request is performed while the publication transaction is open. The publication log is now implemented and tested on the isolated database. A full two-process HTTP and Windows run remains outside this بند and is not claimed here.

## Follow-up verification (2026-10-11)

| Item | Status | Evidence / limitation |
|---|---|---|
| Lease expiry and fencing | Implemented and tested | `claim_batch()` assigns a 30-second token; `acknowledge()` rejects an expired or replaced token. The isolated PostgreSQL transport test still passes. |
| Network outside transaction | Implemented | `SyncTransportWorker.run_once()` commits claim before invoking the sender and acknowledges in a later session. |
| Commit-order-safe publisher ledger | Implemented and tested | `sync_event_publications` and locked per-source counters provide committed publication positions; ordering test passed. |
| HTTP pull/receive/ack contracts | Implemented, not independently exercised | Authenticated routes exist and import successfully; existing tests exercise the service directly. |
| Two independent PostgreSQL HTTP processes | Not tested | The available verified database is `ibn_sina_recovery_test`; no second migrated test database or second API process was created in this run. |
| A → B → C forwarding metadata | Not implemented | The current envelope preserves source identity but has no separate carrier identity/generation fields. |
| Multi-process worker lifecycle | Not tested | The worker is process-safe at the database claim level, but no two-process run, kill/restart test, or Tauri shutdown integration was executed. |
| Medical-table isolation and previous barriers | Tested | Stage-four transport tests and stage-three/phase-two checks pass; receive does not apply inbox rows. |

The database inventory query confirmed the configured PostgreSQL server exposes `ibn_sina_recovery_test` and other existing databases. Existing application databases were not used as transport test targets, and no database was created, migrated, truncated, or dropped during this follow-up. Windows multi-device acceptance remains a later acceptance item. No medical data or secrets were printed.

`recovery_tests/check_publication_ordering.py` passed the three requested scenarios: delayed commit ordering, two concurrent publishers with unique positions, and rollback before commit followed by idempotent retry. The `/sync/v2/pull` route now reads `publication_batch()` using an explicit source identity and publication cursor; it no longer uses `SyncChange.id` for the transport pull path. Network calls remain outside database transactions and inbox application remains disabled.

## Database bootstrap follow-up

The new isolated database bootstrap initially failed in `20260727_01_add_hybrid_permission_system.py` because `permission_service.ensure_seed_data()` flushed through the global stage-three guard. The migration now marks only its private Alembic `Session` with `sync_bootstrap_mode` immediately around reference permission seeding. This context is not read from HTTP, user input, or runtime permission updates; normal uncontracted writes remain fail-closed. The migration also handles transport columns/tables already present in the initial schema without stamping or deleting evidence (`20261007_02`, `20261008_01`, `20261008_02`, `20261008_03`, and `20261008_04`).

On the newly created `ibn_sina_transport_d` database, the command `DATABASE_URL=<same credentials, database changed only> alembic upgrade head` completed successfully through `20261008_04`. The earlier partial `ibn_sina_transport_b` and `ibn_sina_transport_c` databases were not stamped, dropped, or used for clinical data.

The requested two-process HTTP run was not completed after bootstrap because the work window ended before provisioning device identities and launching both API processes. No HTTP success is claimed; the exact prior blocker is fixed and migration success is verified. No medical inbox application or clinic database access occurred.

## HTTP envelope follow-up

`/sync/v2/pull` now invokes `publish_committed()`, prepares the peer delivery claim, and returns complete event envelopes with source identity/generation, revision, content hash, channel metadata, and lease tokens. Receive and ack semantics remain durable-first and lease-bound.

Compilation passed. The direct transport regression was rerun but stopped at its synthetic queue assertion because earlier failed runs left unrelated synthetic `SyncChange` rows ahead of the new row; no broad cleanup was used. A real HTTP receive and invalid-secret 401 test had passed on ports 8811/8812 before this change. The new pull/worker cycle, lost-ACK, and restart tests remain unverified.

The regression cause was isolated to test selection: `queue_for_peer()` did not constrain rows to the requested clinic/generation (and optional source device), so old synthetic changes could compete within the limit. The service now filters by those explicit source identities; it does not alter queue semantics to hide contamination. After the change, `check_postgres_sync_transport.py` passed all existing transport assertions and performed scoped cleanup for its own UUIDs. A complete two-process pull→receive→ack and worker restart run is still not claimed because it requires provisioning and retaining a fresh HTTP fixture after this fix.

## Follow-up status

`source_device_uuid` in `SyncChange`, publication, queue filtering, and inbox is the **origin device** identity. The authenticated HTTP `device` dependency is the receiving/transport peer identity; it is not substituted into the event envelope. The current queue filter therefore prevents clinic/generation/origin mixing while allowing events from another legitimate origin device when that origin is explicitly selected.

The direct transport regression and compilation passed again. The requested new two-database HTTP integration (multi-page pull, receive/ack loss simulation, lease re-claim, worker, and restart) was not executed in this run; no direct-service result is being presented as proof of it. No old rows were deleted, and no medical tables were changed.

## Basic two-database HTTP cycle

`recovery_tests/check_http_cycle.py` starts two independent Uvicorn processes with separate `DATABASE_URL` values (`ibn_sina_recovery_test` and `ibn_sina_transport_d`) on ports 8821 and 8822. It creates one UUID-scoped synthetic `SyncChange`, performs real HTTP `pull`, sends the returned envelope unchanged to `receive`, opens a new PostgreSQL session to verify one `received_waiting_application` inbox row, then sends the returned lease token to `ack`. It verifies the source delivery is `delivered`, the event hash and origin UUID match, and medical-visit counts are unchanged in both databases. The command passed:

```text
python recovery_tests/check_http_cycle.py
PASS HTTP pull -> receive -> durable ack; one inbox row; medical tables unchanged
```

The script terminates both API processes in `finally` and does not print secrets or payload contents. Multi-page interruption, lost HTTP responses, lease re-claim, worker-driven HTTP, and restart persistence remain untested.

## Lost-response HTTP verification

`recovery_tests/check_http_lost_response.py` starts independent APIs on ports 8841/8842 and uses an in-test forwarding proxy that waits for the target response, then closes the client connection. It passed:

```text
PASS receive response cut after destination commit
PASS receive retry duplicate safe
PASS ack response cut after source commit
PASS ack retry idempotent
```

The destination database was checked through a new session and contained exactly one inbox row for the experiment event. The source delivery was `delivered` after the first ack reached the database; repeating the same ack remained successful and did not create another delivery. Medical-visit counts were checked unchanged in the source; inbox receive does not write medical tables. The only transport code change was making an already-`delivered` ack idempotent. Processes and proxy were stopped in `finally`.

## HTTP loopback verification
Two independent API processes were started on 127.0.0.1:8811 and :8812 with separate DATABASE_URL values (the verified recovery database and ibn_sina_transport_d). A real HTTP POST to :8812/api/v1/sync/v2/receive accepted one synthetic event and returned eceived_waiting_application; a wrong device secret returned HTTP 401. The second identical request path was exercised with the same source cursor and no medical application. Processes were stopped after the run. Full pull/ack/worker/fail-ACK multi-batch coverage remains unverified because the current pull contract returns publication identifiers rather than envelopes and the worker does not yet invoke the HTTP receive route.

## Pagination and repeated ACK

acknowledge() retains the final lease token after delivery. Repeated ACKs require the authenticated peer, event, channel, and retained token; a different token is rejected after delivered.

recovery_tests/check_http_pagination.py passed with two APIs on 8861/8862, seven synthetic events, page size two, real pull/receive/ack, one inbox row per event, unchanged medical tables, and wrong-token rejection. check_http_cycle.py and check_http_lost_response.py also passed after the ACK change. Crash/restart pagination with a separately persisted client cursor remains unverified.

## Durable pagination resume

Added protected POST /sync/v2/cursor to read SyncTransportCursor for the authenticated peer/source/generation/channel. check_http_pagination.py now stops both APIs after the first page, starts new processes, reads the cursor through this endpoint, and continues real HTTP pull/receive/ack. It passed with seven events and page size two; all event IDs arrived once, inbox rows remained singular, and medical tables stayed unchanged. The cursor is recovered from PostgreSQL-backed application state, not a file or prior process memory. The synthetic receive rollback hook exists for isolated transaction testing but was not exposed over HTTP; a full failure-point HTTP run remains pending.

## HTTP receive transaction failure

check_http_receive_failure.py uses a dedicated API test process that patches receive_batch in-process once, setting the existing private _fail_before_commit hook after staging the batch and before commit. It is not an HTTP switch. The test passed after an initial stale port process was stopped:

PASS HTTP receive transaction rollback, retry, durable inbox/cursor, medical tables unchanged

A new PostgreSQL session observed zero batch inbox rows and no cursor advance after the failed request; the same envelopes then committed three inbox rows and the cursor on retry, with medical rows unchanged. Processes are stopped in finally. The stale-process cleanup was limited to test Python API processes; no database rows were broadly deleted. Cursor authorization and lease/worker tests remain outside this scope.

## HTTP lease fencing verification

check_http_lease_fencing.py used two independent APIs on 8881/8882 and an internal short-lease process patch (one second, never exposed over HTTP). It passed lease expiry and re-claim with different tokens, stable event UUID/bhash, rejection of the old ACK, durable receive, acceptance of the new ACK, idempotent repeated new ACK, rejection of the old ACK after delivered, invalid cursor authentication, one inbox row, and unchanged medical tables. The basic cycle and lost-response scripts were rerun and passed. The test process was stopped in finally; full worker/Tauri/phase-five work remains out of scope.

## HTTP worker attempt

check_http_worker.py launched independent worker processes using SyncTransportWorker and HTTP receive/ack against APIs on 8891/8892. The run did not pass: only 1/5 synthetic deliveries became delivered; the remaining four returned to pending with NETWORK_TEMPORARY. This is a real worker failure, not a direct-service substitute, and no delivery state was manually changed. The worker processes and APIs were stopped in finally. Medical application was not performed. Root-cause analysis of the sender/ack failure and kill-before-network recovery remains pending.

## Worker diagnosis and fix

Safe diagnostics in _run_http_worker.py showed receive HTTP 200 and ack HTTP 200, followed by a local SYNC_ACK_TOKEN_MISMATCH in SyncTransportWorker. The worker passed string event/token values back to acknowledge(), while the ORM delivery fields are UUID objects; the HTTP ack had already committed, then the local post-network ack compared mismatched Python types and marked the batch temporary. The fix converts event_uuid and lease_token to uuid.UUID before the local idempotent acknowledge. The worker runner now performs bounded run_once cycles through the real SyncTransportWorker until no work remains.

check_http_worker.py was rerun with one worker process and five synthetic events, claim size two. Diagnostics showed three HTTP batches (2,2,1), HTTP receive/ack 200 for each, and all five deliveries became delivered. The destination contained one inbox row per event and medical tables were unchanged. No competition or kill/restart was run in this task.

## Worker ACK and kill/resume follow-up

The worker now treats the HTTP ACK as the single writer of source delivery state; it no longer performs a second local acknowledge. UUID strings are converted at the worker boundary. Sender HTTP status/response-count diagnostics are safe (no bodies/secrets), and protocol/auth/conflict failures are classified permanent instead of NETWORK_TEMPORARY.

The kill-after-claim test was attempted with two APIs, a one-second internal lease, and a real worker process. It failed at the coordination assertion: no sending row was observed within the 0.5-second window before the worker exited, so no kill-after-committed-claim evidence was produced. No delivery state or token was manually changed. Basic HTTP and lost-response tests were rerun and passed. Kill/resume remains unverified.

## Deterministic worker kill/resume

Added optional internal after_claim callback to SyncTransportWorker; normal runs leave it unset. _run_http_worker.py uses it only when WORKER_COORDINATE is set by the test process: it emits event UUIDs after the claim transaction commits and waits on a local release file before sender. check_http_worker.py now waits for that signal, verifies sending/lease state, kills the worker process forcibly before any network request, waits beyond the one-second test lease, and starts a new real worker. The resumed worker completed three HTTP batches (2,2,1), all five deliveries became delivered, and the destination contained one inbox row per event with unchanged medical tables. No delivery states or tokens were manually changed. Basic HTTP/lost-response tests remain passing.

## Scope correction and competition/transaction status

The prior worker result is now labeled worker kill/resume; it did not assert competing workers. check_http_worker.py reran successfully with that corrected label. The runner can optionally log claim records (worker_id, event_uuid, lease_token, timestamp) to a test-only file, but a two-process competition run and NOWAIT/HTTP-delay transaction-boundary run were not executed in this task. No claim-safety or idle-in-transaction conclusion is being claimed from the kill/resume test.

## Competing-worker verification

check_http_worker_competition.py launched two real worker processes for the same peer/channel, each paused after committed claim with separate gates. PostgreSQL showed non-empty sending claims with unique event UUIDs and live lease tokens; no event was claimed by both workers. After release, one worker delivered three events, while the other received HTTP 500 for a higher-sequence batch arriving before the lower batch; two deliveries returned to pending with NETWORK_TEMPORARY. This exposes an ordering/cursor coordination defect under concurrent delivery, not a network outage. The test is therefore a failure, not proof of complete competition safety. No states/tokens were manually changed and medical tables were not applied.

## Concurrent cursor race fix

Captured API stderr identified the 500: psycopg.errors.UniqueViolation (SQLSTATE 23505) on uq_sync_transport_cursor when concurrent receivers both observed no cursor and attempted INSERT. The fix uses PostgreSQL INSERT ... ON CONFLICT DO NOTHING followed by SELECT ... FOR UPDATE, preserving atomic inbox/cursor behavior. The earlier limit(1) event lookup was removed; terminal event_uuid is derived from the channel-scoped batch that advanced the cursor, while cursor coverage is computed from durable source sequences without max(sequence).

check_http_worker_competition.py now passes: both workers claimed non-empty disjoint event sets with live tokens, both HTTP receive/ack paths returned 200, all five deliveries became delivered, and destination inbox/medical isolation checks passed. Pagination and lost-response HTTP scripts were rerun and passed. The competition script output label should be renamed from placeholder in a future cleanup; the assertions and result are real.

## Cursor semantic review

The current receive cursor is explicitly SyncTransportCursor.last_source_sequence; receive and gap coverage use SyncEventInbox.source_sequence. The publication log has a separate publish_sequence, but it is not carried in the envelope or stored in inbox, so the new HTTP pull path does not yet provide a publication-position cursor. last_event_uuid is derived from the terminal event in the contiguous source-sequence coverage, not from an arbitrary final request item. Pagination and rollback scripts were previously passing on this source-sequence contract; a deterministic out-of-order publication-position test is not claimed until the envelope/inbox/cursor contract is migrated to carry publication position.

## Publication cursor contract update (2026-10-11)

- Migration `20261008_05` adds `sync_publication_receipts`; `20261008_06` adds `last_publish_sequence` and `last_publication_event_uuid` to `sync_transport_cursors` and a unique publication-position constraint.
- Event identity (`event_uuid`, origin device/generation, `source_sequence`, and `content_sha256`) is immutable. `publish_sequence` is allocated independently per source generation/channel and is carried only as publication metadata; lease tokens are transport state and are excluded from the content hash.
- The receive transaction stores the immutable inbox row (or verifies its hash), the per-channel publication receipt, and advances the publication cursor only across contiguous durable receipt positions. Older source cursors remain for compatibility and are not used as the transport cursor.
- Pull returns full envelopes and publication page metadata. Missing publication rows are rejected with `SYNC_PUBLICATION_MISSING`; incomplete envelopes are not acknowledged.
- Verified on isolated PostgreSQL databases `ibn_sina_recovery_test` and `ibn_sina_transport_d` (both Alembic `20261008_06`): direct transport checks and HTTP pull -> receive -> ack passed, with one inbox row and no medical-table changes. The full out-of-order HTTP coverage, multi-channel receipt test, and restart/rollback matrix remain pending and are not claimed here.

## Deterministic publication-gap verification (2026-10-11)

Script: `backend/recovery_tests/check_http_publication_gap.py`.

- Verified Alembic chain on both isolated databases: `20261008_04 -> 20261008_05 -> 20261008_06`; the new migration is directly down-revisioned to `20261008_05`, not stamped.
- Created four synthetic events with sparse `source_sequence` values (10, 30, 90, 140). Their publication positions were independently allocated as 1..4 for a fresh channel.
- Pulled two real pages over HTTP, received the newer page first, and verified two inbox rows and two publication receipts while the durable cursor remained at publish position 0.
- Restarted both APIs and read `/sync/v2/cursor` from PostgreSQL; the gap remained at 0. Receiving the older page advanced the cursor to 4 and set `last_publication_event_uuid` to the event at publication position 4.
- Replayed both pages; inbox and receipt counts remained four. Medical rows were unchanged and all inbox rows remained waiting for application.

This proves the out-of-order gap behavior for the tested channel. It does not yet cover a new event after the final cursor, same event through two channels, or the complete unauthorized-position and receive-rollback matrix.

## Channel independence verification (2026-10-11)

Script: `backend/recovery_tests/check_http_publication_channels.py`.

- The same synthetic event and content hash crossed `central_server` and `mobile_server` over separate HTTP pulls. Destination state contained one inbox row and two independent publication receipts.
- Each channel maintained its own cursor and publication position. Lease and channel metadata were not part of the immutable content hash.
- A new event published after the first channel cursor was recovered by a later pull without replaying the original event.
- Reusing an occupied publication position for a different event returned `409 SYNC_PUBLICATION_POSITION_CONFLICT`; the existing receipt and cursor were unchanged.
- Medical tables were unchanged and inbox events remained waiting for application.

The gap, channel, and HTTP cycle scripts passed after the service change. Full unauthorized-range and receive-rollback coverage remains pending.

## Publication scope and receive atomicity verification (2026-10-11)

Script: `backend/recovery_tests/check_http_scope_and_receive_atomic.py`.

- HTTP authorization checks rejected an invalid device secret, a valid device claiming another source identity, a foreign clinic, and a cursor request from another peer. No unauthorized response exposed event data; the cursor was scoped to the authenticated peer.
- The tested valid scope (authenticated receiver, authorized source device, matching clinic/generation/channel) succeeded.
- Three isolated internal runner hooks exercised failure after inbox insertion, after publication-receipt insertion, and after cursor calculation before commit. Fresh PostgreSQL sessions showed no partial inbox rows, receipts, cursor advancement, or delivery acknowledgement after each failure. Retrying without the hook stored the full batch and ACK completed idempotently.
- Medical rows were compared before and after and remained unchanged. Hooks are process-local test instrumentation and are not HTTP controls.

## Final-contract worker/lease recheck (2026-10-11)

- `check_http_worker.py` passed after correcting its isolated fixture to publish up to 1000 rows before queueing; the worker delivered five sparse-source-sequence events through HTTP, and the destination contained one inbox row per event with no medical-table changes.
- `check_http_lease_fencing.py` passed, including new lease token fencing and cursor authorization.
- `check_http_worker_competition.py` was attempted but did not reach both `after_claim` gates; it remains unproven under the final publication contract. No claim or delivery result is reported from that run.
- The requested delayed-response/`FOR UPDATE NOWAIT` proof that the claim transaction is closed before network I/O was not executed in this run.

## Competition diagnosis (2026-10-11)

The previous competition fixture could queue deliveries for events that had not yet received a publication row because `publish_committed` scanned the oldest global `SyncChange` rows and a bounded batch could be exhausted by unrelated historical rows. `claim_batch` correctly rejected those rows with `SYNC_PUBLICATION_MISSING`; this was a fixture/data-selection failure, not a network failure.

The publisher query was tightened to exclude events already published for the requested channel, so repeated publishing can progress past unrelated rows. The competition runner now verifies publication rows and eligible deliveries by the experiment event UUIDs and captures worker stdout/stderr with bounded waits. The run still did not reach both `after_claim` gates before the bounded diagnostic wait, so competing claims are not claimed as proven. No delivery states or tokens were manually changed.

## Transaction boundary verification (2026-10-11)
- Added ackend/recovery_tests/_run_http_gate_proxy.py and check_http_worker_transaction_boundary.py.
- On isolated ibn_sina_transport_d source and destination test setup (destination API configured separately), a real worker request was observed at the proxy before response release. An independent PostgreSQL session saw the committed sending claim and successfully acquired the same delivery row with FOR UPDATE NOWAIT, then rolled back, proving the claim transaction was not held during network wait.
- After release, the worker completed HTTP receive/ack: one delivered delivery, one inbox row, one publication receipt, and no medical rows changed. Viewing services on 8811/8812 were not used or stopped.
- This verifies one-worker transaction boundaries only; multi-worker contention, lease recovery, A->B->C, Windows/Tauri remain unverified in this check.

## Durable relay foundation (2026-10-11)
- Added migration 20261008_07_shared_transport_events and model SyncTransportEvent, a canonical immutable transport source for local committed events and verified inbox events. Receive now records an inbox event in this source within the same transaction; local publication backfills the source without creating a medical SyncChange.
- The full A?B?C relay is intentionally not enabled yet: publication/claim still require explicit relay authorization and publisher identity fields, so no three-node network test was run. This avoids treating an inbox row as a local medical change.

## SyncTransportEvent verification (2026-10-11)
- Verified Alembic 20261008_06 -> 20261008_07 on the configured isolated PostgreSQL test database; migration created sync_transport_events and its source index. No clinic database or destructive cleanup was used.
- A synthetic committed SyncChange was published through the real publish_committed; a new session observed one canonical SyncTransportEvent row with the original event/source identities. Python compile checks passed.
- Full inbox duplicate/content-mismatch, concurrent receive, rollback, and publication-gap reruns were not claimed here. The current publisher/claim path still does not consume inbox-origin events or carry an independent relay publisher identity, so full A->B->C remains disabled.

## SyncTransportEvent safety verification (2026-10-11)
- Added repeatable ackend/recovery_tests/check_sync_transport_event_safety.py and verified on the isolated ibn_sina_recovery_test PostgreSQL database.
- Real eceive_batch produced one inbox row, one canonical source row, one publication receipt, and a durable cursor; a new session confirmed persistence and zero medical rows.
- Matching retry returned duplicates=1. Payload/content and source-identity changes were rejected without replacing the original source. Two concurrent sessions produced one canonical row with accepted/duplicate outcomes and no unhandled unique violation.
- Internal failure hooks after canonical source, inbox, receipt, and cursor stages rolled back; no partial source/inbox/receipt remained for those synthetic events. Full relay remains disabled.

## Relay identity and authorization foundation (2026-10-11)
- Added migration 20261008_08_relay_identity_scope: durable sync_relay_authorizations (default deny, carrier/origin-generation/destination/channel scope) and nullable publisher identity fields on publication rows. Existing publication rows are preserved and are not assigned guessed publisher identities.
- Added SyncRelayAuthorization model and SyncTransportService.authorize_relay; the isolated test confirmed default denial, explicit scope acceptance, and wrong-channel rejection.
- Publisher/claim integration with SyncTransportEvent and full A->B->C forwarding remains deliberately disabled. No inbox event is applied or converted to SyncChange; no three-node test was run.

## Relay engine linkage (2026-10-11)
- Added publish_relay_event() with explicit scope authorization and separate publisher identity fields in envelopes/publications; claim_batch() can now build an envelope from SyncTransportEvent when a delivery exists, without creating SyncChange.
- Existing local transport and authorization checks still pass (check_relay_identity_scope.py, compileall).
- queue_for_peer() still enumerates SyncChange only, and publication counters/receipt uniqueness remain origin-scoped for legacy compatibility. Therefore inbox-to-peer queueing and a complete relay claim path are not declared complete; no A->B->C test was run. Further migration/integration is required before enabling relay production paths.

## Publisher-scoped queue/claim verification (2026-10-11)
- Added migration 20261008_09_publisher_scoped_transport plus 20261008_10_restore_legacy_receipt_constraint; publisher identity columns and indexes were added without deleting legacy data. The legacy receipt constraint was restored after testing exposed that old receive idempotency still depends on it.
- queue_for_peer now includes published canonical transport events, and claim_batch reads the canonical source when no SyncChange exists. A real isolated test accepted an inbox-origin event under explicit relay scope, assigned a publisher-local position, queued it, and claimed one envelope retaining the origin while reporting the publisher separately.
- Tests: python backend/recovery_tests/check_relay_publish_queue_claim.py passed (publish=1, queue=1, claim_count=1); check_sync_transport_event_safety.py passed after migrations. No A->B->C HTTP network was run; medical tables were not modified.

## Publisher scope contract (2026-10-11)
- Added migration 20261008_11_publisher_scope_contract with clinic and publisher fields on receipts/cursors/deliveries, publisher-scope indexes/constraints, and historical_scope_status for legacy rows. Legacy rows remain nullable/ambiguous and are excluded from new publisher coverage until explicitly mapped.
- Receive now records publisher metadata from the envelope when present and updates the cursor clinic/publisher fields; legacy receive remains accepted only for compatibility and does not invent publisher identity.
- Safety and relay publish/queue/claim scripts pass after the migration. Full HTTP scope enforcement, publisher-aware pull/cursor/ack contracts, and A->B->C remain unverified and are not enabled.

## Strict publisher-scope HTTP contract (2026-10-11)
- Confirmed Alembic current is 20261008_11 with down revision chain ending 20261008_10 -> 20261008_11.
- Transport schemas now require contract version 2.1 and publisher device/generation/clinic for receive, pull, cursor, and ack. Missing scope is rejected by validation; receive also rejects missing/mismatched publisher metadata before durable writes.
- ACK now checks authenticated peer plus publisher scope against the delivery row.
- Compile checks passed. Existing legacy HTTP scripts that omit publisher scope are intentionally incompatible and were not reported as passing; they require contract updates before rerun. Full two-database HTTP gap/independent-publisher testing remains outstanding.

## Contract 2.1 HTTP check (2026-10-11)
- Confirmed Alembic head 20261008_11; strict schemas require contract version 2.1 and publisher device/generation/clinic on receive, pull, cursor, and ack. Receive validates publisher metadata before writes; ACK checks delivery scope.
- Updated the source safety fixture to send publisher fields; PostgreSQL receive/source tests pass.
- Existing check_http_cycle.py was run and failed before HTTP with ConnectionRefusedError on 127.0.0.1:8821 because it does not provision/start its API processes; no HTTP result was claimed. The viewing services were not touched. Full HTTP cycle remains unverified.

## HTTP contract 2.1 cycle verification (2026-10-11)
- check_http_cycle.py now independently upgrades both isolated databases to Alembic head, starts Uvicorn on 8821/8822 with separate DATABASE_URL values, captures per-process logs, waits on /openapi.json, and stops only its own processes.
- Requests now include contract_version 2.1 and publisher clinic/device/generation fields. The real HTTP cycle passed: pull -> receive -> durable cursor -> ack; one inbox row, unchanged medical tables, and delivered source delivery were verified.
- Previous failure was a real schema mismatch on the destination (sync_transport_cursors.publisher_device_uuid missing), fixed by migrating both databases independently. Scope rejection matrix remains a separate follow-up; no A->B->C was run.

## HTTP publisher-scope rejection matrix (2026-10-11)
- check_http_cycle.py now verifies each isolated database identity/schema/Alembic head, migrates both independently, starts APIs on 8821/8822, waits for OpenAPI readiness, and stops only its own processes.
- Actual HTTP results: missing publisher 422; old contract 422; invalid device credential 401; receive publisher mismatch 409; wrong ACK token 409; repeated valid ACK 200. No 500 occurred. The successful cycle retained one inbox row, durable delivery, and unchanged medical tables.
- The script currently does not claim the full foreign-cursor and revoked-scope matrix; those require a dedicated authorized multi-peer fixture. Viewing services were untouched.

## Peer authorization isolation update (2026-10-11)
- Pull, receive, cursor, and ack now invoke the persistent relay authorization check using the authenticated carrier device; cycle fixtures create an explicit scope for the authorized peer.
- The cycle rejection matrix was rerun successfully after this change. A dedicated P/Q two-peer HTTP fixture was not run in this check; no claim is made for foreign-cursor isolation beyond the authorization gate itself.

## P/Q peer isolation verification (2026-10-11)
- Added check_http_peer_scope_isolation.py, an independent two-peer HTTP fixture using isolated databases and APIs on 8831/8832. It creates distinct P and Q scopes and stops only its own processes.
- Actual results: P pull 200; Q own scope pull 200; Q foreign pull 403; Q foreign receive 403; Q foreign cursor 403; Q foreign ACK 403; PostgreSQL snapshot unchanged for rejected destination requests; medical rows unchanged.
- The test does not cover revocation during an active claim or A->B->C. check_http_cycle.py rejection wording now distinguishes accepted repeated ACK (200) from rejected cases.

## Relay authorization revocation check (2026-10-11)
- Added check_relay_revocation.py. The implemented policy is default-deny after revocation; an existing sending claim remains durable and is not deleted or marked delivered. ACK after revocation is expected to be rejected by the HTTP authorization gate until reconciliation/regrant.
- Real service test: publish=1, queue=1, claim_count=1, revoke, subsequent authorization returned Forbidden (403), and the existing delivery remained sending. No medical tables were changed.
- This check did not run a coordinated HTTP worker kill/resume or post-receive-before-ACK scenario; those remain unverified.

## Revocation after claim before network (2026-10-11)
- Added a efore_send reauthorization callback to the real SyncTransportWorker; it runs after the committed claim and before the first HTTP request. Revocation failures are classified as permanent, not NETWORK_TEMPORARY.
- check_http_worker_revocation_before_send.py passed: proxy gate observed the claim, scope was revoked, callback blocked the HTTP send, no destination inbox/receipt was created, source was not delivered, and the delivery retained its durable non-delivered state.
- The test did not cover the separate receive-before-ACK revocation policy or regrant/resume.

## Revocation after claim / explicit resume (2026-10-11)
- Added SyncTransportService.resume_relay_delivery, which requires restored relay authorization and only requeues TRANSPORT_PERMANENT deliveries; content/protocol errors remain non-resumable.
- Extended check_http_worker_revocation_before_send.py: after claim and revocation, before_send blocks HTTP; authorization is restored and the delivery is requeued through the service, without editing status/token manually.
- The separate receive-committed-before-ACK scenario and full worker HTTP completion after regrant remain unverified in this check.
