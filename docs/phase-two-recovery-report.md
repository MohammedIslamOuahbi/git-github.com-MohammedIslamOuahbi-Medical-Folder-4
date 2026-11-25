# Stage 2: recovery capture register

This stage adds an additive PostgreSQL recovery register. It does not run the migration, read a clinic database, apply recovered records, change device mode/API routing, or lift the stage-one sync barriers.

## Verified inventory from source code

| Expected source | Existing code | Capture support added | Actually captured in this session |
|---|---|---|---|
| Zustand queue persisted at `clinic_sync_queue` and `clinic_sync_meta` | `frontend/src/store/syncStore.ts`, `frontend/src/utils/storage.ts` | Manual browser snapshot | No |
| Medical form drafts under `medical-folder.worker-medical-file.*` | `frontend/src/pages/workspace/WorkerMedicalFilePage.tsx` | Manual browser snapshot, always review-only | No |
| Mission manifest and central run/cursor context in localStorage | `frontend/src/hooks/useMissionOperations.ts`, `frontend/src/utils/storage.ts` | Preserved as snapshot context, never medical operation | No |
| Legacy `.sync`/`.json` package | `backend/app/services/client_sync_service.py`, `backend/app/services/client_sync_import_service.py` | Manual file capture up to 16 MiB; no import | No |
| PostgreSQL `sync_changes`, `client_sync_changes`, `client_local_sync_runs`, `client_local_sync_state`, `device_sync_states`, `sync_conflicts` | Corresponding models and journals | Admin-only page capture, replayable from ID zero | No |
| Tauri `runtime-state.json`, `client-local-copy.json`, `backend.env`, backup folder | `frontend/src-tauri/src/main.rs` | Inventory only. `backend.env` may contain secrets and must not be copied into the register. | No |
| Browser tokens, device credential, central device secret | `frontend/src/utils/storage.ts` | Deliberately excluded; authentication data is not a recovery source | No |

This is an inventory of paths in code. Browser profiles, installed Windows applications, other devices, and real packages were not enumerated. Existing create-mode code in `WorkerMedicalFilePage.tsx` can delete its draft key; stage-two capture itself does not delete or change any existing key, but users should capture that profile before continuing workflows that may replace its drafts.

## Capture semantics

- Browser capture reads an allowlist of existing keys without calling their JSON helper, which may remove malformed values. It compares two reads and aborts if storage changes during hashing. A new `clinic_recovery_profile_uuid` key identifies the browser profile; existing keys are untouched. The request is written to whichever FastAPI API is currently configured. It does not make a remote-mode client local; local-only capture awaits the approved later stage.
- File capture reads selected UTF-8 `.sync` or `.json` content. The file is not modified. Files over 16 MiB, binary attachments, and raw Tauri runtime files are not covered yet. A package's public `server_id` is recorded only as a claim.
- Journal capture uses the installation UUID stored in PostgreSQL; if it is missing or ambiguous, capture fails rather than guessing a database identity. Each page is bounded. Repeating from the first page is safe because captured page snapshots are deduplicated.
- The raw source snapshot is stored first and committed before item interpretation. Items are registered in batches of 100. An interrupted registration resumes from the committed ordinal. The API returns metadata only, and the existing logging middleware logs method, path, and elapsed time, not request bodies.
- Recognized credential fields are rejected before storage. This is not a general encrypted archive; access to PostgreSQL and its backups must remain restricted because recovered medical source data is stored there.

## States and identity

`captured`: raw source was committed, but item registration has not finished. `recorded`: all items have been registered and await the unified engine; no clinical application happened. `needs_review`: source or item is malformed, lacks an established identity, contains a numeric relationship, is a draft, or needs human interpretation. Individual items are `waiting_engine` or `needs_review`. Reason codes are returned without raw content.

Snapshot uniqueness uses `(source_scope, source_kind, logical_key, sha256)` in PostgreSQL. A changed snapshot of the same logical source links to its previous snapshot. Item uniqueness uses `(source_uuid, ordinal)`; two identical queue entries at different indices remain two entries. For entries without stable IDs, the identity is the **snapshot UUID plus position and source reference**. That position does not claim the same logical operation across changed snapshots. A raw source remains the byte-preserving authority; interpreted item fragments are parsed representations with a reference back to it.

The candidate identity table stores `(capture scope, entity type, old ID, UUID, item)` only when both old ID and UUID appear in a non-draft business item. Candidates stay `candidate_needs_review`; no numerical foreign key or revision ancestry is inferred. PostgreSQL journal event IDs are not mapped to medical entity UUIDs. Claimed package identities and browser-provided device IDs are not verified database identities.

## Files and database

- `backend/app/models/legacy_recovery.py`: `recovery_sources`, `recovery_items`, `recovery_identity_candidates`.
- `backend/alembic/versions/20261007_01_add_recovery_register.py`: additive migration after `20260823_01`; downgrade refuses silent deletion of preserved evidence.
- `backend/app/services/recovery_format.py`: checksum, format validation, safe interpretation.
- `backend/app/services/legacy_recovery_service.py`: durable source commit, bounded registration, access control, journal page capture, metadata summaries.
- `backend/app/schemas/legacy_recovery.py`, `backend/app/routers/legacy_recovery.py`: authenticated capture/resume/list endpoints.
- `backend/app/models/__init__.py`, `backend/app/main.py`: model registration and router inclusion.
- `frontend/src/services/legacyRecovery.ts`, `frontend/src/pages/sync-connection/RecoveryPanel.tsx`, and `SyncConnectionPage.tsx`: manual capture and metadata-only status display.
- Isolated tests: `backend/recovery_tests/test_recovery.py`, `frontend/scripts/test-recovery-capture.mjs`.

## Test status and limits

The recovery tests use synthetic content and an in-memory session double, **not SQLite**. They check duplicate snapshots, changed versions, distinct identical entries, interrupted capture/resume, malformed or mismatched content, claimed origins, numeric collisions, missing identity, access rejection, and unchanged browser keys. A real HTTP router test rejects unauthenticated requests and foreign-source reads using overridden dependencies without a database connection. Stage-one tests remain in place.

The initial migration now excludes the three recovery tables through `TABLES_OWNED_BY_LATER_REVISIONS`, so the additive recovery revision owns their creation. On the isolated local PostgreSQL database `ibn_sina_recovery_test`, read-only identity checks observed `current_database() = ibn_sina_recovery_test`, schema `public`, local port 5432, PostgreSQL 18.4, and `alembic current` returned `20261007_01 (head)`. The recovery tables existed and had zero rows before the integration check. The application `users` and `workers` tables also had zero rows. The connection URL/password were not printed. **The schema was already present; these observations alone were not treated as evidence of successful persistence.** No migration was executed during this verification.

The opt-in integration check at `backend/recovery_tests/check_postgres_recovery.py` then exercised the real SQLAlchemy models and `LegacyRecoveryService` using uniquely scoped synthetic sources. It passed all of the following against independent PostgreSQL sessions: a committed source and two items survived reopening the connection; repeated capture made no duplicate source or item; a changed snapshot linked to its predecessor; identical content at two positions remained two items; a simulated interruption after the raw-source commit resumed in 100/5-item batches without loss or duplication; mismatched SHA-256 and unsupported format were rejected without inserts; numeric ID 7 from two source scopes produced separate review-only identity candidates. Both an ordinary two-connection concurrent capture and a forced simultaneous first-commit uniqueness race returned one source and three items. These tests exercise database persistence and uniqueness in this environment, but do not prove behavior for all crash points or distributed network failures.

The same integration check used FastAPI `TestClient` with actual PostgreSQL sessions: unauthenticated capture/browse returned 401, a different user could not inspect or resume the source (403), and authorized metadata endpoints omitted `raw_payload`, `raw_fragment`, and the synthetic raw snapshot. Row counts of every non-recovery application table were identical before and after the check. Cleanup deleted only rows whose source scope contained this run's random identifier; subsequent read-only counts of all three recovery tables were zero. No original browser keys, drafts, or package files were used or deleted. No recovered item was applied to a medical table. No SQLite, `drop_all`, `create_all`, `TRUNCATE`, restore, or migration replay was used.

One repeat run exposed an ordering bug in the **test cleanup**, not in capture: deleting a parent snapshot before its changed child violated the recovery self-foreign-key. The test was corrected to delete child snapshots first. The six sources from that failed run were identified by their exact random source-scope prefix, synthetic logical key, and creator UUID, then deleted with their own items/candidates only. The corrected integration test passed on rerun, and a separate read-only query again found zero rows in all three recovery tables.

The phase-one isolated checks were rerun: five backend Python, six frontend Node, and two extracted Rust checks passed. The phase-two isolated tests (12 Python) also passed. The prior Windows sidecar and installer binaries were not rebuilt. The previous full Cargo check failed while unpacking an unavailable dependency; the isolated Rust tests do not prove that an installed application is protected.

No clinic source was captured, no old source was deleted, and no item was applied to medical tables during this work. The stage-one guards remain active. This check does not establish the state of other devices or installed binaries.
