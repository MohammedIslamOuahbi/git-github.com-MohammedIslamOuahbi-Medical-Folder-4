# Installation Profile Upgrade Path

This project now persists a local `installation_state` record for each installation UUID.

Upgrade behavior:

- Existing databases keep all current business data unchanged.
- The migration creates `installation_state` rows only as `unconfigured`.
- No existing installation is silently promoted to `central_server`.
- If a legacy `sync_device` already exists, its `device_uuid`, `device_code`, and `device_name` are copied into the new record.
- If a related `central_server_state` exists, its server UUID metadata is copied for reference only. The profile still remains `unconfigured` until provisioning confirms it.

Recommended upgrade flow:

1. Create a PostgreSQL safety backup before the first post-upgrade launch.
2. Run `alembic upgrade head`.
3. Launch the backend.
4. Let the installer-provisioned profile configure fresh installs automatically.
5. For older installs with no trusted installer profile, keep the installation unconfigured until an administrator explicitly confirms whether it is a `central_server` or a `mobile_device`.

Operational note:

- A trusted installer hint may provision fresh installs automatically.
- A configured installation profile is immutable unless the installation is explicitly reset or reinstalled.
