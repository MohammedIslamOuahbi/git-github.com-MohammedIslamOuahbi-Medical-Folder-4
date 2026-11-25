# Manual Acceptance Guide — medical-folder-4

This guide covers implemented behavior only. Leave “Actual result” blank until the reviewer performs the case and records evidence. Use the isolated development test databases only; never use the clinic database or patient data.

## 0. Setup and boundaries

Verify that `ibn_sina_recovery_test` and `ibn_sina_transport_d` are the intended test databases, and record each schema and Alembic head without printing `DATABASE_URL` or secrets. Keep `127.0.0.1:8811`, `8812`, `5171`, and `5172` running. Viewing credentials remain in `backend/recovery_tests/.stage4-view-credentials.json`; never copy them into a report.

Supporting scripts are evidence tools, not substitutes for manual review: `check_http_cycle.py`, `check_http_lost_response.py`, `check_http_receive_failure.py`, `check_http_pagination.py`, `check_http_publication_gap.py`, `check_http_publication_channels.py`, `check_http_lease_fencing.py`, `check_http_worker.py`, `check_http_worker_competition.py`, and `check_http_worker_transaction_boundary.py`. Use fresh experiment IDs. Do not modify delivery states manually.

## 1. Setup and authentication

| ID | Role | Link | Steps | Expected | Evidence | Actual result |
|---|---|---|---|---|---|---|
| AUTH-01 | All roles | 5171 / Setup | Open Setup, verify “Adresse API résolue”, run the connection check, then change the address and check again. | Both display and request use `http://127.0.0.1:8811/api/v1`; checking does not save settings. | Address and Network screenshots. | |
| AUTH-02 | All roles | 5172 / Setup | Repeat AUTH-01 for the second instance. | Both display and request use `http://127.0.0.1:8812/api/v1`, independently. | Screenshot and Network evidence. | |
| AUTH-03 | super_admin, admin, doctor, assistant | 8811 and 8812 `/auth/login` | Log in with each existing test account, then try a wrong password. | Correct credentials succeed; wrong credentials are rejected without disclosure. | HTTP status, `/auth/me`, `/auth/me/permissions`. | |
| AUTH-04 | All roles | Both UIs | Log out, open a protected page, and call `/auth/me` again. | Unauthorized access is rejected. | 401/403 and screenshot. | |
| AUTH-05 | All roles | Both UIs | Compare role/permission rows before and after login. | Login does not modify role or permission data; resolution is user override, then role, then default deny. | Row snapshots or hashes. | |

## 2. Protected local writes

Use the UI for available paths. If the UI does not expose `expected_version` or `operation_uuid`, use that same server’s Swagger; do not invent an endpoint.

| ID | Role | Link | Steps | Expected | Evidence | Actual result |
|---|---|---|---|---|---|---|
| WRITE-01 | doctor/admin | Workers and medical visits | Create and edit a synthetic record through the UI. | Local API save succeeds. | Status and experiment UUID. | |
| WRITE-02 | doctor | Protected edit path | Open the same record in two windows and submit edits from the same version. | One succeeds; the other returns 409 and preserves the rejected attempt without changing the record. | Record version, 409, attempt record. | |
| WRITE-03 | doctor/admin | Swagger edit path | Retry the same `operation_uuid` with identical content, then with different content. | Identical retry has no extra effect; different content is rejected. | Safe result and row count. | |
| WRITE-04 | Authorized user | Edit-attempt path | View attempts as an authorized and unauthorized account. | Authorized users see status without raw payload; unauthorized users receive 403. | Status and response fields. | |
| WRITE-05 | Any user | Signed-document path | Try to edit a signed document. | Rejected; original remains unchanged. | Status and original hash. | |

## 3. Data-safety guards

| ID | Role | Link/tool | Steps | Expected | Evidence | Actual result |
|---|---|---|---|---|---|---|
| GUARD-01 | admin | Suspended CRUD path | Send a suspended operational write. | `423 OPERATION_SUSPENDED_FOR_DATA_SAFETY`, `retryable=false`, no write. | Status and table snapshot. | |
| GUARD-02 | admin | Legacy sync paths | Try legacy push/run or old package import. | Rejected or suspended; queue is neither cleared nor falsely reported successful. | Response and queue snapshots. | |
| GUARD-03 | admin | Backup API | Run status/create/restore/export-usb in development. | Failure inside the Tauri/service result is shown as failure; no fake valid backup is added. | Result and backup list. | |
| GUARD-04 | Reviewer | Development build | Separate API/React behavior from the old sidecar/installer. | The old Tauri build is not treated as updated or validated. | Build/process information. | |

## 4. Recovery register

Use `check_postgres_recovery.py` and `/recovery/sources`, `/recovery/sources/{id}/items`, `/recovery/sources/{id}/resume` with a unique synthetic source.

| ID | Role | Link/tool | Steps | Expected | Evidence | Actual result |
|---|---|---|---|---|---|---|
| REC-01 | Authorized | Recovery API | Capture a synthetic queue/draft, then inspect the source. | Source and fingerprint are stored without changing the source. | Counts/fingerprint only; no raw payload. | |
| REC-02 | Authorized | Recovery API | Capture the same source again. | No duplicate source or item. | Source ID and counts. | |
| REC-03 | Authorized | Recovery API | Change the source and capture it again. | New version is linked to the previous version; old version remains. | Link/status. | |
| REC-04 | Authorized | Resume | Interrupt item recording, then resume. | No loss or duplication; statuses remain captured/stored/needs review. | Item statuses. | |
| REC-05 | Unauthorized | Recovery API | Request sources and items with an unauthorized account. | 403 without raw content. | Status and absent sensitive fields. | |
| REC-06 | Reviewer | PostgreSQL | Compare medical tables before and after recovery cases. | No recovered item is medically applied. | Row-content snapshots/hashes. | |

## 5. New HTTP transport

Run these scripts only with isolated test databases and fresh IDs. ACK means durable receipt only; it does not mean medical application.

| ID | Role/party | Tool or link | Steps | Expected | Evidence | Actual result |
|---|---|---|---|---|---|---|
| TR-01 | Source/peer device | `check_http_cycle.py` | Pull, receive, then ACK over real HTTP. | Envelope, fingerprint, and event UUID match; one inbox row; source delivery is delivered. | New PostgreSQL sessions. | |
| TR-02 | Peers | `check_http_lost_response.py` | Cut the receive response after commit, retry the envelope; repeat for lost ACK response. | No duplicate; delivery state remains correct. | One inbox row and delivered state. | |
| TR-03 | Peers | `check_http_pagination.py` | Transfer multiple pages, stop services/client, then resume. | `has_more` and durable cursor are correct; no loss or skip. | Cursor read from PostgreSQL. | |
| TR-04 | Peers | `check_http_publication_gap.py` | Send the newer page before the older page, restart, then fill the gap. | Events are stored; cursor stays before the gap, then advances after coverage completes. | Publication cursor fields. | |
| TR-05 | Two authorized channels | `check_http_publication_channels.py` | Transfer the same event through two channels with different positions. | One inbox row, independent receipt and cursor per channel. | Receipt/cursor counts. | |
| TR-06 | Unauthorized peer | `check_http_scope_and_receive_atomic.py` | Try invalid credentials, source/generation/channel outside authorization, and position collision. | Clear rejection; no partial inbox/receipt/cursor. | Status codes and before/after snapshots. | |
| TR-07 | Peer | `check_http_lease_fencing.py` | Obtain a lease, let it expire, then send old and new tokens. | Old token rejected; new token succeeds; event fingerprint unchanged. | Claim/lease/token rows. | |
| TR-08 | One worker | `check_http_worker.py` | Run the real worker for several batches. | All events delivered; one inbox row each. | Delivery and receipt rows. | |
| TR-09 | Killed worker | Worker hook scenario | Stop after claim and before network, then start a new worker after lease expiry. | New claim token and resume without duplication. | Claim, lease, inbox, delivery. | |
| TR-10 | Two workers | `check_http_worker_competition.py` | Start two independent workers with an IPC barrier and pause after claims. | Claims are disjoint and tokens valid; transfer completes. | Claim rows, not only inbox count. | |
| TR-11 | One worker | `check_http_worker_transaction_boundary.py` | Delay the proxy response; run NOWAIT on the delivery row while waiting, then release. | Lock succeeds, proving claim transaction ended before network. | Script output and medical snapshot. | |

## 6. Running and stopping tools

From the repository root:

```powershell
python backend/recovery_tests/check_http_cycle.py
python backend/recovery_tests/check_http_pagination.py
python backend/recovery_tests/check_http_worker_transaction_boundary.py
```

For scripts that start APIs or proxies, use their documented settings and ports other than 8811/8812. Stop only PIDs created by the script; do not use broad process termination. Do not publish logs containing secrets.

## 7. Error record template

```text
Test ID:
Role/device (no secret):
Database identity (name only):
Experiment ID:
Steps:
Expected:
Actual:
HTTP status / safe error code:
Evidence (experiment UUIDs and timestamps only):
Process/command:
Were medical rows applied? yes/no/unknown:
Cleanup performed:
```

## 8. Not proven or out of scope

This guide does not establish clinical readiness. Field-server outage, complete provisioning of data/attachments/accounts, A ? B ? C transport, Tauri integration, and the installed Windows build require separate validation. A single integration run does not prove every CRUD route or attachment size. Do not start phase five or lift any guards based on this guide.
