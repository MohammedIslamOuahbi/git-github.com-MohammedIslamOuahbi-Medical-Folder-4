import { spawnSync } from "node:child_process";

const profile = process.argv[2] ?? "desktop";
const result = spawnSync("cmd.exe", ["/c", "scripts\\tauri-build-msvc.cmd"], {
  cwd: process.cwd(),
  stdio: "inherit",
  env: {
    ...process.env,
    TAURI_INSTALLATION_PROFILE: profile,
  },
});

process.exit(result.status ?? 1);

