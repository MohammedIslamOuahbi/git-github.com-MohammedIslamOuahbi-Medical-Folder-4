import { spawnSync } from "node:child_process";

const result = spawnSync("cmd.exe", ["/c", "scripts\\tauri-build-msvc.cmd"], {
  cwd: process.cwd(),
  stdio: "inherit",
  env: process.env,
});

process.exit(result.status ?? 1);

