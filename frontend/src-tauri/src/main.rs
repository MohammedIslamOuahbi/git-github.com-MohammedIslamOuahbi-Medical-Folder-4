#![allow(non_snake_case)]

use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::net::UdpSocket;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{de::DeserializeOwned, Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, Manager, State};

const LOCAL_SERVER_API_BASE_URL: &str = "http://127.0.0.1:8000/api/v1";
const LOCAL_SERVER_ROOT_URL: &str = "http://127.0.0.1:8000";
const DEFAULT_SERVER_HOST: &str = "0.0.0.0";
const DEFAULT_SERVER_PORT: u16 = 8000;
const DEFAULT_POSTGRES_PORT: u16 = 5432;
const DEFAULT_POSTGRES_DB: &str = "medical_folder";

struct AppState {
    backend_child: Mutex<Option<Child>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            backend_child: Mutex::new(None),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
struct RuntimeStateRecord {
    operation_mode: Option<String>,
    connection_mode: Option<String>,
    server_url: Option<String>,
    backup_folder: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DesktopRuntimeContext {
    is_tauri: bool,
    operation_mode: String,
    connection_mode: String,
    deployment_state: Option<String>,
    api_base_url: String,
    server_api_url: String,
    local_ip_address: Option<String>,
    backend_status: String,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DeploymentInspection {
    state: String,
    server_runtime_config_exists: bool,
    server_runtime_config_valid: bool,
    client_server_url_exists: bool,
    local_copy_config_exists: bool,
    operation_mode: String,
    connection_mode: String,
    server_api_url: Option<String>,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PostgresInspection {
    installed: bool,
    psql_path: Option<String>,
    service_name: Option<String>,
    service_status: Option<String>,
    local_ip_address: Option<String>,
    runtime_config_path: String,
    runtime_config_exists: bool,
    bundled_config_exists: bool,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ServerBootstrapPayload {
    provisioning_capability: String,
    host: String,
    port: u16,
    admin_user: String,
    admin_password: String,
    app_database: String,
    app_user: String,
    app_user_password: String,
    api_bind_host: String,
    api_port: u16,
    open_firewall: bool,
    initial_admin_first_name: String,
    initial_admin_last_name: String,
    initial_admin_email: String,
    initial_admin_password: String,
    initial_admin_phone: Option<String>,
    initial_admin_qualification: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ProvisioningCapabilityResponse {
    capability: String,
    expires_in_seconds: u32,
    deployment_state: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ServerBootstrapResult {
    success: bool,
    step: String,
    message: String,
    details: Vec<String>,
    lan_ip: Option<String>,
    api_url: Option<String>,
    database_ready: bool,
    migration_applied: bool,
    import_applied: bool,
    firewall_rule_applied: bool,
    config_path: Option<String>,
    warning: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ServerResetResult {
    success: bool,
    state: String,
    database_preserved: bool,
    runtime_config_removed: bool,
    client_local_copy_preserved: bool,
    backups_preserved: bool,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ClientLocalCopyConfigPayload {
    host: String,
    port: u16,
    database_name: String,
    user: String,
    password: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ClientLocalCopyInspection {
    configured: bool,
    host: Option<String>,
    port: Option<u16>,
    database_name: Option<String>,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ClientSyncImportRequest {
    package_payload: Value,
    expected_server_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ClientSyncImportResult {
    success: bool,
    server_id: Option<String>,
    from_cursor: Option<i64>,
    to_cursor: Option<i64>,
    inserted_count: Option<i64>,
    updated_count: Option<i64>,
    deleted_count: Option<i64>,
    skipped_count: Option<i64>,
    file_count: Option<i64>,
    attachment_count: Option<i64>,
    checksum_sha256: Option<String>,
    package_id: Option<String>,
    package_name: Option<String>,
    summary: Option<Value>,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ClientSyncPackagePreview {
    valid: bool,
    selected_path: Option<String>,
    package_id: Option<String>,
    package_name: Option<String>,
    checksum_sha256: Option<String>,
    server_id: Option<String>,
    from_cursor: Option<i64>,
    to_cursor: Option<i64>,
    created_at: Option<String>,
    application_version: Option<String>,
    schema_version: Option<i64>,
    workspace: Option<Value>,
    record_counts: Option<BTreeMap<String, i64>>,
    tombstone_count: Option<i64>,
    attachment_count: Option<i64>,
    duplicate: Option<bool>,
    summary: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ClientSyncHistoryEnvelope {
    history: Vec<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ClientSyncLocalStatus {
    configured: bool,
    server_id: Option<String>,
    last_sync_cursor: Option<i64>,
    last_sync_at: Option<String>,
    last_package_id: Option<String>,
    last_package_name: Option<String>,
    last_imported_at: Option<String>,
    last_package_checksum: Option<String>,
    schema_version: Option<i64>,
    last_status: Option<String>,
    history_count: Option<i64>,
    imported_rows_total: Option<i64>,
    skipped_rows_total: Option<i64>,
    latest_run: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PostgresBackupToolsInspection {
    pg_dump_available: bool,
    pg_restore_available: bool,
    pg_dump_path: Option<String>,
    pg_restore_path: Option<String>,
    postgres_bin_directory: Option<String>,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PostgresBackupFile {
    filename: String,
    path: String,
    created_at: Option<String>,
    size_bytes: u64,
    format: String,
    status: String,
    checksum_sha256: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PostgresBackupStatus {
    device_mode: String,
    server_actions_available: bool,
    backup_folder: Option<String>,
    backup_folder_writable: bool,
    tools: PostgresBackupToolsInspection,
    operation_state: String,
    backups: Vec<PostgresBackupFile>,
    last_backup_time: Option<String>,
    last_backup_status: String,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PostgresBackupOperationResult {
    success: bool,
    operation_state: String,
    message: String,
    backup: Option<PostgresBackupFile>,
    safety_backup: Option<PostgresBackupFile>,
    destination_path: Option<String>,
    checksum_sha256: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SelectedBackupFile {
    filename: String,
    path: String,
    size_bytes: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct FinalizeServerSetupPayload {
    mode: String,
    backup_path: Option<String>,
    confirmation_phrase: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct FinalizeServerSetupResult {
    success: bool,
    state: String,
    message: String,
    detail: String,
    completed: bool,
    active_step: String,
    steps: Vec<String>,
    selected_backup: Option<SelectedBackupFile>,
    safety_backup: Option<PostgresBackupFile>,
}

fn main() {
    tauri::Builder::default()
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            get_runtime_context,
            inspect_deployment_state,
            apply_operation_mode,
            start_backend_sidecar,
            stop_backend_sidecar,
            inspect_postgres_installation,
            begin_server_provisioning,
            bootstrap_server_postgres,
            reset_server_configuration,
            inspect_client_local_copy,
            configure_client_local_copy,
            import_client_sync,
            import_client_sync_package_file,
            import_client_sync_package_path,
            preview_client_sync_package_file,
            get_client_sync_import_history,
            get_client_sync_local_status,
            inspect_postgres_backup_tools,
            get_postgres_backup_status,
            choose_backup_directory,
            open_backup_directory,
            create_postgres_backup,
            validate_postgres_backup,
            choose_server_restore_backup_file,
            finalize_server_setup,
            restore_postgres_backup,
            export_backup_to_usb,
        ])
        .run(tauri::generate_context!())
        .expect("failed to run tauri application");
}

fn runtime_root(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_local_data_dir()
        .map_err(|error| error.to_string())?;
    fs::create_dir_all(&dir).map_err(|error| error.to_string())?;
    Ok(dir)
}

fn runtime_state_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(runtime_root(app)?.join("runtime-state.json"))
}

fn backend_env_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(runtime_root(app)?.join("backend.env"))
}

fn client_local_copy_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(runtime_root(app)?.join("client-local-copy.json"))
}

fn read_runtime_state(app: &AppHandle) -> RuntimeStateRecord {
    let Ok(path) = runtime_state_path(app) else {
        return RuntimeStateRecord::default();
    };

    match fs::read_to_string(path) {
        Ok(content) => serde_json::from_str(&content).unwrap_or_default(),
        Err(_) => RuntimeStateRecord::default(),
    }
}

fn write_runtime_state(app: &AppHandle, state: &RuntimeStateRecord) -> Result<(), String> {
    let path = runtime_state_path(app)?;
    let content = serde_json::to_string_pretty(state).map_err(|error| error.to_string())?;
    fs::write(path, content).map_err(|error| error.to_string())
}

fn write_text_file(path: &Path, content: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    fs::write(path, content).map_err(|error| error.to_string())
}

fn normalize_server_root(url: Option<String>) -> String {
    url.unwrap_or_default().trim().trim_end_matches('/').to_string()
}

fn default_operation_mode(state: &RuntimeStateRecord) -> String {
    match state.connection_mode.as_deref() {
        Some("SERVER_PC") => "server".to_string(),
        Some("CLIENT") | Some("SERVER") => "client".to_string(),
        _ => match state.operation_mode.as_deref() {
        Some("server") => "server".to_string(),
        _ => "client".to_string(),
        },
    }
}

fn default_connection_mode(state: &RuntimeStateRecord) -> String {
    match state.connection_mode.as_deref() {
        Some("CLIENT") | Some("SERVER_PC") | Some("SERVER") => state.connection_mode.clone().unwrap_or_default(),
        _ if default_operation_mode(state) == "client" => "CLIENT".to_string(),
        _ => "SERVER_PC".to_string(),
    }
}

fn current_local_ip() -> Option<String> {
    let socket = UdpSocket::bind("0.0.0.0:0").ok()?;
    socket.connect("8.8.8.8:80").ok()?;
    let addr = socket.local_addr().ok()?;
    Some(addr.ip().to_string())
}

fn backend_status(state: &State<'_, AppState>) -> String {
    match state.backend_child.lock() {
        Ok(guard) => {
            if guard.is_some() {
                "Running".to_string()
            } else {
                "Stopped".to_string()
            }
        }
        Err(_) => "Failed".to_string(),
    }
}

fn load_backend_env_map(app: &AppHandle) -> BTreeMap<String, String> {
    let mut values = BTreeMap::new();
    let Ok(path) = backend_env_path(app) else {
        return values;
    };

    let Ok(content) = fs::read_to_string(path) else {
        return values;
    };

    for line in content.lines() {
        if line.trim().is_empty() || line.trim_start().starts_with('#') {
            continue;
        }
        if let Some((key, value)) = line.split_once('=') {
            values.insert(key.trim().to_string(), value.trim().to_string());
        }
    }

    values
}

fn compute_runtime_context(app: &AppHandle, state: &State<'_, AppState>, message: String) -> DesktopRuntimeContext {
    let stored = read_runtime_state(app);
    let operation_mode = default_operation_mode(&stored);
    let connection_mode = default_connection_mode(&stored);
    let server_api_url = if operation_mode == "server" {
        LOCAL_SERVER_ROOT_URL.to_string()
    } else {
        normalize_server_root(stored.server_url.clone())
    };
    let api_base_url = if operation_mode == "server" {
        LOCAL_SERVER_API_BASE_URL.to_string()
    } else if server_api_url.is_empty() {
        "http://0.0.0.0:0/api/v1".to_string()
    } else {
        format!("{server_api_url}/api/v1")
    };

    DesktopRuntimeContext {
        is_tauri: true,
        operation_mode,
        connection_mode,
        deployment_state: Some(resolve_deployment_state(app)),
        api_base_url,
        server_api_url,
        local_ip_address: current_local_ip(),
        backend_status: backend_status(state),
        message,
    }
}

fn resolve_deployment_state(app: &AppHandle) -> String {
    let runtime = read_runtime_state(app);
    let mode = default_operation_mode(&runtime);
    let has_backend_env = backend_env_path(app).map(|path| path.exists()).unwrap_or(false);
    let has_client_url = runtime.server_url.as_deref().map(|value| !value.trim().is_empty()).unwrap_or(false);

    if mode == "server" && has_backend_env {
        "server-configured".to_string()
    } else if mode == "client" && has_client_url {
        "client-configured".to_string()
    } else {
        "unconfigured".to_string()
    }
}

fn find_program(name: &str) -> Option<String> {
    let output = Command::new("where").arg(name).stdout(Stdio::piped()).stderr(Stdio::null()).output().ok()?;
    if !output.status.success() {
        return None;
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let first = stdout
        .lines()
        .map(str::trim)
        .find(|line| !line.is_empty())?;
    Some(first.to_string())
}

fn sidecar_candidates(app: &AppHandle) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(resource_dir) = app.path().resource_dir() {
        candidates.push(resource_dir.join("medical-backend-sidecar-x86_64-pc-windows-msvc.exe"));
        candidates.push(resource_dir.join("medical-backend-sidecar.exe"));
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    candidates.push(manifest_dir.join("bin").join("medical-backend-sidecar-x86_64-pc-windows-msvc.exe"));
    candidates.push(manifest_dir.join("bin").join("medical-backend-sidecar.exe"));
    candidates
}

fn resolve_sidecar_path(app: &AppHandle) -> Result<PathBuf, String> {
    sidecar_candidates(app)
        .into_iter()
        .find(|candidate| candidate.exists())
        .ok_or_else(|| "Bundled backend sidecar not found. Run npm run build:backend first.".to_string())
}

fn run_sidecar_json<T: DeserializeOwned>(
    app: &AppHandle,
    args: &[&str],
) -> Result<T, String> {
    let binary = resolve_sidecar_path(app)?;
    let output = Command::new(binary)
        .args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|error| error.to_string())?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let message = if !stderr.is_empty() { stderr } else { stdout };
        return Err(if message.is_empty() {
            "Sidecar command failed.".to_string()
        } else {
            message
        });
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let payload = stdout
        .lines()
        .rev()
        .find(|line| line.trim_start().starts_with('{'))
        .ok_or_else(|| "Sidecar command returned no JSON payload.".to_string())?;
    serde_json::from_str(payload).map_err(|error| error.to_string())
}

fn render_backend_env(payload: &ServerBootstrapPayload) -> String {
    let db_host = if payload.host.trim().is_empty() {
        "127.0.0.1".to_string()
    } else {
        payload.host.trim().to_string()
    };
    let db_port = if payload.port == 0 { DEFAULT_POSTGRES_PORT } else { payload.port };
    let app_database = if payload.app_database.trim().is_empty() {
        DEFAULT_POSTGRES_DB.to_string()
    } else {
        payload.app_database.trim().to_string()
    };
    let api_port = if payload.api_port == 0 { DEFAULT_SERVER_PORT } else { payload.api_port };
    let api_host = if payload.api_bind_host.trim().is_empty() {
        DEFAULT_SERVER_HOST.to_string()
    } else {
        payload.api_bind_host.trim().to_string()
    };

    format!(
        concat!(
            "APP_ENV=production\n",
            "BACKEND_HOST={api_host}\n",
            "BACKEND_PORT={api_port}\n",
            "API_BASE_URL=http://127.0.0.1:{api_port}/api/v1\n",
            "DATABASE_URL=postgresql+psycopg2://{app_user}:{app_password}@{db_host}:{db_port}/{db_name}\n",
            "BACKEND_CORS_ORIGINS=tauri://localhost,http://tauri.localhost,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000\n",
            "APP_NAME=Ibn Sina Medical Clinic\n",
            "INITIAL_ADMIN_FIRST_NAME={first_name}\n",
            "INITIAL_ADMIN_LAST_NAME={last_name}\n",
            "INITIAL_ADMIN_EMAIL={email}\n",
            "INITIAL_ADMIN_PASSWORD={password}\n",
            "INITIAL_ADMIN_PHONE={phone}\n",
            "INITIAL_ADMIN_QUALIFICATION={qualification}\n"
        ),
        api_host = api_host,
        api_port = api_port,
        app_user = payload.app_user.trim(),
        app_password = payload.app_user_password.trim(),
        db_host = db_host,
        db_port = db_port,
        db_name = app_database,
        first_name = payload.initial_admin_first_name.trim(),
        last_name = payload.initial_admin_last_name.trim(),
        email = payload.initial_admin_email.trim(),
        password = payload.initial_admin_password.trim(),
        phone = payload.initial_admin_phone.clone().unwrap_or_default().trim().to_string(),
        qualification = payload
            .initial_admin_qualification
            .clone()
            .unwrap_or_default()
            .trim()
            .to_string(),
    )
}

fn file_modified_iso(path: &Path) -> Option<String> {
    let metadata = fs::metadata(path).ok()?;
    let modified = metadata.modified().ok()?;
    let seconds = modified.duration_since(UNIX_EPOCH).ok()?.as_secs();
    Some(seconds.to_string())
}

fn file_to_backup(path: &Path) -> Option<PostgresBackupFile> {
    // Keep historical files on disk, but never list placeholder .txt files as backups.
    if !matches!(path.extension().and_then(|ext| ext.to_str()), Some("backup" | "dump" | "sql")) {
        return None;
    }
    let metadata = fs::metadata(path).ok()?;
    if !metadata.is_file() { return None; }
    Some(PostgresBackupFile {
        filename: path.file_name()?.to_string_lossy().to_string(),
        path: path.to_string_lossy().to_string(),
        created_at: file_modified_iso(path),
        size_bytes: metadata.len(),
        format: path.extension().map(|ext| ext.to_string_lossy().to_string()).unwrap_or_else(|| "bin".to_string()),
        status: "ready".to_string(),
        checksum_sha256: None,
    })
}

#[tauri::command]
fn get_runtime_context(app: AppHandle, state: State<'_, AppState>) -> Result<DesktopRuntimeContext, String> {
    Ok(compute_runtime_context(&app, &state, String::new()))
}

#[tauri::command]
fn inspect_deployment_state(app: AppHandle) -> Result<DeploymentInspection, String> {
    let runtime = read_runtime_state(&app);
    let mode = default_operation_mode(&runtime);
    let connection_mode = default_connection_mode(&runtime);
    let backend_env = backend_env_path(&app)?;
    let client_copy = client_local_copy_path(&app)?;
    let server_url = normalize_server_root(runtime.server_url.clone());

    Ok(DeploymentInspection {
        state: resolve_deployment_state(&app),
        server_runtime_config_exists: backend_env.exists(),
        server_runtime_config_valid: backend_env.exists(),
        client_server_url_exists: !server_url.is_empty(),
        local_copy_config_exists: client_copy.exists(),
        operation_mode: mode,
        connection_mode,
        server_api_url: if server_url.is_empty() { None } else { Some(server_url) },
        message: "Desktop runtime inspection completed.".to_string(),
    })
}

#[tauri::command]
fn apply_operation_mode(
    app: AppHandle,
    state: State<'_, AppState>,
    mode: String,
    serverUrl: Option<String>,
) -> Result<DesktopRuntimeContext, String> {
    let mut runtime = read_runtime_state(&app);
    let connection_mode = match mode.as_str() {
        "SERVER" | "server" => "SERVER",
        "SERVER_PC" => "SERVER_PC",
        "CLIENT" | "client" => "CLIENT",
        _ => "SERVER_PC",
    };
    let operation_mode = if connection_mode == "SERVER_PC" { "server" } else { "client" };
    runtime.operation_mode = Some(operation_mode.to_string());
    runtime.connection_mode = Some(connection_mode.to_string());
    if operation_mode == "client" {
        runtime.server_url = serverUrl.map(|value| value.trim().trim_end_matches('/').to_string());
    }
    write_runtime_state(&app, &runtime)?;
    Ok(compute_runtime_context(&app, &state, "Operation mode updated.".to_string()))
}

#[tauri::command]
fn start_backend_sidecar(app: AppHandle, state: State<'_, AppState>) -> Result<DesktopRuntimeContext, String> {
    let mut guard = state.backend_child.lock().map_err(|_| "Failed to access backend process state.".to_string())?;
    if guard.is_none() {
        let binary = resolve_sidecar_path(&app)?;
        let child = Command::new(binary)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| format!("Failed to start backend sidecar: {error}"))?;
        *guard = Some(child);
    }
    drop(guard);
    Ok(compute_runtime_context(&app, &state, "Backend sidecar started.".to_string()))
}

#[tauri::command]
fn stop_backend_sidecar(app: AppHandle, state: State<'_, AppState>) -> Result<DesktopRuntimeContext, String> {
    let mut guard = state.backend_child.lock().map_err(|_| "Failed to access backend process state.".to_string())?;
    if let Some(child) = guard.as_mut() {
        let _ = child.kill();
    }
    *guard = None;
    drop(guard);
    Ok(compute_runtime_context(&app, &state, "Backend sidecar stopped.".to_string()))
}

#[tauri::command]
fn inspect_postgres_installation(app: AppHandle) -> Result<PostgresInspection, String> {
    let psql_path = find_program("psql.exe");
    let runtime_config = backend_env_path(&app)?;
    Ok(PostgresInspection {
        installed: psql_path.is_some(),
        psql_path,
        service_name: None,
        service_status: None,
        local_ip_address: current_local_ip(),
        runtime_config_path: runtime_config.to_string_lossy().to_string(),
        runtime_config_exists: runtime_config.exists(),
        bundled_config_exists: runtime_config.exists(),
        message: "PostgreSQL inspection completed.".to_string(),
    })
}

#[tauri::command]
fn begin_server_provisioning(app: AppHandle) -> Result<ProvisioningCapabilityResponse, String> {
    Ok(ProvisioningCapabilityResponse {
        capability: "desktop-local".to_string(),
        expires_in_seconds: 300,
        deployment_state: resolve_deployment_state(&app),
    })
}

#[tauri::command]
fn bootstrap_server_postgres(app: AppHandle, request: ServerBootstrapPayload) -> Result<ServerBootstrapResult, String> {
    let env_path = backend_env_path(&app)?;
    write_text_file(&env_path, &render_backend_env(&request))?;

    let mut runtime = read_runtime_state(&app);
    runtime.operation_mode = Some("server".to_string());
    runtime.connection_mode = Some("SERVER_PC".to_string());
    write_runtime_state(&app, &runtime)?;

    let lan_ip = current_local_ip();
    let api_url = lan_ip
        .as_ref()
        .map(|ip| format!("http://{ip}:{}", if request.api_port == 0 { DEFAULT_SERVER_PORT } else { request.api_port }));

    Ok(ServerBootstrapResult {
        success: true,
        step: "write-runtime-config".to_string(),
        message: "Runtime PostgreSQL configuration saved for the desktop sidecar.".to_string(),
        details: vec![
            format!("Config written to {}", env_path.to_string_lossy()),
            "Run the final server setup step to apply Alembic and seed the initial admin.".to_string(),
        ],
        lan_ip,
        api_url,
        database_ready: false,
        migration_applied: false,
        import_applied: false,
        firewall_rule_applied: false,
        config_path: Some(env_path.to_string_lossy().to_string()),
        warning: Some("This rebuilt Tauri shell does not auto-create PostgreSQL users yet; verify the database credentials before first launch.".to_string()),
    })
}

#[tauri::command]
fn reset_server_configuration(app: AppHandle, confirmationPhrase: String) -> Result<ServerResetResult, String> {
    if confirmationPhrase.trim() != "RESET" {
        return Ok(ServerResetResult {
            success: false,
            state: resolve_deployment_state(&app),
            database_preserved: true,
            runtime_config_removed: false,
            client_local_copy_preserved: true,
            backups_preserved: true,
            message: "Type RESET to confirm server configuration reset.".to_string(),
        });
    }

    let env_path = backend_env_path(&app)?;
    if env_path.exists() {
        let _ = fs::remove_file(&env_path);
    }

    let mut runtime = read_runtime_state(&app);
    runtime.operation_mode = Some("client".to_string());
    runtime.connection_mode = Some("CLIENT".to_string());
    runtime.server_url = None;
    write_runtime_state(&app, &runtime)?;

    Ok(ServerResetResult {
        success: true,
        state: "unconfigured".to_string(),
        database_preserved: true,
        runtime_config_removed: true,
        client_local_copy_preserved: true,
        backups_preserved: true,
        message: "Desktop server runtime configuration removed.".to_string(),
    })
}

#[tauri::command]
fn inspect_client_local_copy(app: AppHandle) -> Result<ClientLocalCopyInspection, String> {
    let path = client_local_copy_path(&app)?;
    if !path.exists() {
        return Ok(ClientLocalCopyInspection {
            configured: false,
            host: None,
            port: None,
            database_name: None,
            message: "Client local copy is not configured.".to_string(),
        });
    }

    let content = fs::read_to_string(path).map_err(|error| error.to_string())?;
    let payload: ClientLocalCopyConfigPayload = serde_json::from_str(&content).map_err(|error| error.to_string())?;
    Ok(ClientLocalCopyInspection {
        configured: true,
        host: Some(payload.host),
        port: Some(payload.port),
        database_name: Some(payload.database_name),
        message: "Client local copy configuration found.".to_string(),
    })
}

#[tauri::command]
fn configure_client_local_copy(
    app: AppHandle,
    request: ClientLocalCopyConfigPayload,
) -> Result<ClientLocalCopyInspection, String> {
    let path = client_local_copy_path(&app)?;
    let content = serde_json::to_string_pretty(&request).map_err(|error| error.to_string())?;
    write_text_file(&path, &content)?;
    Ok(ClientLocalCopyInspection {
        configured: true,
        host: Some(request.host),
        port: Some(request.port),
        database_name: Some(request.database_name),
        message: "Client local copy configuration saved.".to_string(),
    })
}

#[tauri::command]
fn import_client_sync(_request: ClientSyncImportRequest) -> Result<ClientSyncImportResult, String> {
    Ok(ClientSyncImportResult {
        success: false,
        server_id: None,
        from_cursor: None,
        to_cursor: None,
        inserted_count: None,
        updated_count: None,
        deleted_count: None,
        skipped_count: None,
        file_count: None,
        attachment_count: None,
        checksum_sha256: None,
        package_id: None,
        package_name: None,
        summary: None,
        message: "Direct in-memory package import is not available in the rebuilt Tauri shell yet. Use the file-based import flow.".to_string(),
    })
}

#[tauri::command]
fn import_client_sync_package_file(
    _app: AppHandle,
    _expectedServerId: Option<String>,
) -> Result<ClientSyncImportResult, String> {
    Ok(ClientSyncImportResult {
        success: false,
        server_id: None,
        from_cursor: None,
        to_cursor: None,
        inserted_count: None,
        updated_count: None,
        deleted_count: None,
        skipped_count: None,
        file_count: None,
        attachment_count: None,
        checksum_sha256: None,
        package_id: None,
        package_name: None,
        summary: None,
        message: "Native file picker support is not rebuilt yet. Use import_client_sync_package_path with a selected file path.".to_string(),
    })
}

#[tauri::command]
fn import_client_sync_package_path(
    app: AppHandle,
    packagePath: String,
    _expectedServerId: Option<String>,
) -> Result<ClientSyncImportResult, String> {
    let _ = (app, packagePath);
    Err("OPERATION_SUSPENDED_FOR_DATA_SAFETY: Package import suspended; no sidecar was started.".to_string())
}

#[tauri::command]
fn preview_client_sync_package_file(
    _app: AppHandle,
    _expectedServerId: Option<String>,
) -> Result<ClientSyncPackagePreview, String> {
    Ok(ClientSyncPackagePreview {
        valid: false,
        selected_path: None,
        package_id: None,
        package_name: None,
        checksum_sha256: None,
        server_id: None,
        from_cursor: None,
        to_cursor: None,
        created_at: None,
        application_version: None,
        schema_version: None,
        workspace: None,
        record_counts: None,
        tombstone_count: None,
        attachment_count: None,
        duplicate: None,
        summary: None,
    })
}

#[tauri::command]
fn get_client_sync_import_history(app: AppHandle) -> Result<ClientSyncHistoryEnvelope, String> {
    run_sidecar_json::<ClientSyncHistoryEnvelope>(&app, &["--client-sync-history"])
}

#[tauri::command]
fn get_client_sync_local_status(app: AppHandle) -> Result<ClientSyncLocalStatus, String> {
    run_sidecar_json::<ClientSyncLocalStatus>(&app, &["--client-sync-status"])
}

#[tauri::command]
fn inspect_postgres_backup_tools() -> Result<PostgresBackupToolsInspection, String> {
    let pg_dump_path = find_program("pg_dump.exe");
    let pg_restore_path = find_program("pg_restore.exe");
    let postgres_bin_directory = pg_dump_path
        .as_deref()
        .and_then(|value| Path::new(value).parent())
        .map(|path| path.to_string_lossy().to_string());

    Ok(PostgresBackupToolsInspection {
        pg_dump_available: pg_dump_path.is_some(),
        pg_restore_available: pg_restore_path.is_some(),
        pg_dump_path,
        pg_restore_path,
        postgres_bin_directory,
        message: "Backup tools inspection completed.".to_string(),
    })
}

#[tauri::command]
fn get_postgres_backup_status(app: AppHandle) -> Result<PostgresBackupStatus, String> {
    let runtime = read_runtime_state(&app);
    let tools = inspect_postgres_backup_tools()?;
    let backup_folder = runtime.backup_folder.clone();
    let backup_path = backup_folder.clone().map(PathBuf::from);
    let backups = backup_path
        .as_ref()
        .and_then(|folder| fs::read_dir(folder).ok())
        .into_iter()
        .flat_map(|entries| entries.flatten())
        .filter_map(|entry| file_to_backup(&entry.path()))
        .collect::<Vec<_>>();

    let backup_folder_writable = backup_path
        .as_ref()
        .map(|path| path.exists())
        .unwrap_or(false);

    Ok(PostgresBackupStatus {
        device_mode: default_operation_mode(&runtime),
        server_actions_available: backend_env_path(&app)?.exists(),
        backup_folder,
        backup_folder_writable,
        tools,
        operation_state: resolve_deployment_state(&app),
        last_backup_time: backups.first().and_then(|file| file.created_at.clone()),
        last_backup_status: if backups.is_empty() { "idle" } else { "ready" }.to_string(),
        message: "Backup status collected.".to_string(),
        backups,
    })
}

#[tauri::command]
fn choose_backup_directory(app: AppHandle) -> Result<PostgresBackupStatus, String> {
    let selected = runtime_root(&app)?.join("backups");
    fs::create_dir_all(&selected).map_err(|error| error.to_string())?;
    let mut runtime = read_runtime_state(&app);
    runtime.backup_folder = Some(selected.to_string_lossy().to_string());
    write_runtime_state(&app, &runtime)?;
    get_postgres_backup_status(app)
}

#[tauri::command]
fn open_backup_directory(app: AppHandle) -> Result<(), String> {
    let runtime = read_runtime_state(&app);
    let Some(folder) = runtime.backup_folder else {
        return Err("No backup directory configured.".to_string());
    };

    Command::new("explorer")
        .arg(folder)
        .spawn()
        .map_err(|error| error.to_string())?;
    Ok(())
}

#[tauri::command]
fn create_postgres_backup(_app: AppHandle) -> Result<PostgresBackupOperationResult, String> {
    Ok(suspended_backup_result())
}

fn suspended_backup_result() -> PostgresBackupOperationResult {
    PostgresBackupOperationResult {
        success: false,
        operation_state: "OPERATION_SUSPENDED_FOR_DATA_SAFETY".to_string(),
        message: "OPERATION_SUSPENDED_FOR_DATA_SAFETY: PostgreSQL backup creation is suspended until a real, verified implementation is available. No backup file was created.".to_string(),
        backup: None,
        safety_backup: None,
        destination_path: None,
        checksum_sha256: None,
    }
}

#[tauri::command]
fn validate_postgres_backup(backupPath: String) -> Result<PostgresBackupFile, String> {
    file_to_backup(Path::new(&backupPath)).ok_or_else(|| "Backup file not found.".to_string())
}

#[tauri::command]
fn choose_server_restore_backup_file() -> Result<SelectedBackupFile, String> {
    Err("Native backup file picker support is not rebuilt yet.".to_string())
}

#[tauri::command]
fn finalize_server_setup(
    app: AppHandle,
    request: FinalizeServerSetupPayload,
) -> Result<FinalizeServerSetupResult, String> {
    let upgrade_result = run_sidecar_json::<Value>(&app, &["--alembic-upgrade"]);
    let bootstrap_result = run_sidecar_json::<Value>(&app, &["--application-bootstrap"]);

    let success = upgrade_result.is_ok() && bootstrap_result.is_ok();
    let detail = if success {
        "Alembic upgrade and application bootstrap completed.".to_string()
    } else {
        format!(
            "Upgrade result: {:?}. Bootstrap result: {:?}.",
            upgrade_result.err(),
            bootstrap_result.err()
        )
    };

    Ok(FinalizeServerSetupResult {
        success,
        state: if success { "configured" } else { "failed" }.to_string(),
        message: if success {
            "Server setup completed.".to_string()
        } else {
            "Server setup did not complete successfully.".to_string()
        },
        detail,
        completed: success,
        active_step: if success { "done" } else { "bootstrap" }.to_string(),
        steps: vec![
            "Write backend.env".to_string(),
            "Run Alembic upgrade".to_string(),
            "Bootstrap application data".to_string(),
        ],
        selected_backup: request.backup_path.as_ref().and_then(|path| {
            fs::metadata(path).ok().map(|metadata| SelectedBackupFile {
                filename: Path::new(path)
                    .file_name()
                    .map(|value| value.to_string_lossy().to_string())
                    .unwrap_or_else(|| "backup".to_string()),
                path: path.clone(),
                size_bytes: metadata.len(),
            })
        }),
        safety_backup: None,
    })
}

#[tauri::command]
fn restore_postgres_backup(
    _request: Value,
) -> Result<PostgresBackupOperationResult, String> {
    Ok(PostgresBackupOperationResult {
        success: false,
        operation_state: "not-implemented".to_string(),
        message: "Automated PostgreSQL restore has not been rebuilt in this Tauri shell yet.".to_string(),
        backup: None,
        safety_backup: None,
        destination_path: None,
        checksum_sha256: None,
    })
}

#[cfg(test)]
mod tests {
    use super::{default_connection_mode, default_operation_mode, RuntimeStateRecord};

    #[test]
    fn v2_connection_mode_survives_runtime_state_round_trip() {
        let state = RuntimeStateRecord {
            operation_mode: Some("server".to_string()),
            connection_mode: Some("SERVER_PC".to_string()),
            server_url: None,
            backup_folder: Some("C:\\runtime\\backups".to_string()),
        };

        let encoded = serde_json::to_string(&state).expect("runtime state should serialize");
        let restored: RuntimeStateRecord = serde_json::from_str(&encoded).expect("runtime state should deserialize");

        assert_eq!(default_connection_mode(&restored), "SERVER_PC");
        assert_eq!(restored.operation_mode.as_deref(), Some("server"));
    }

    #[test]
    fn v2_connection_role_controls_transport_resolution() {
        let server_pc = RuntimeStateRecord {
            operation_mode: Some("client".to_string()),
            connection_mode: Some("SERVER_PC".to_string()),
            server_url: None,
            backup_folder: None,
        };
        let server = RuntimeStateRecord {
            operation_mode: Some("server".to_string()),
            connection_mode: Some("SERVER".to_string()),
            server_url: Some("http://192.168.1.10:8000".to_string()),
            backup_folder: None,
        };

        assert_eq!(default_operation_mode(&server_pc), "server");
        assert_eq!(default_operation_mode(&server), "client");
    }
}

#[tauri::command]
fn export_backup_to_usb(
    _request: Value,
) -> Result<PostgresBackupOperationResult, String> {
    Ok(PostgresBackupOperationResult {
        success: false,
        operation_state: "not-implemented".to_string(),
        message: "USB backup export has not been rebuilt in this Tauri shell yet.".to_string(),
        backup: None,
        safety_backup: None,
        destination_path: None,
        checksum_sha256: None,
    })
}
