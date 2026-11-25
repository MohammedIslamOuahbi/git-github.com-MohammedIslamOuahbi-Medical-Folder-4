import { existsSync, mkdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";

const root = process.cwd();
const keyDir = path.join(root, ".tauri");
const privateKeyPath = path.join(keyDir, "updater.key");
const publicKeyPath = `${privateKeyPath}.pub`;

if (!existsSync(keyDir)) {
  mkdirSync(keyDir, { recursive: true });
}

if (existsSync(privateKeyPath) && existsSync(publicKeyPath)) {
  process.exit(0);
}

const result = spawnSync(
  "cmd.exe",
  [
    "/c",
    ".\\node_modules\\.bin\\tauri.cmd",
    "signer",
    "generate",
    "--ci",
    "--force",
    "-w",
    privateKeyPath,
    "-p",
    "",
  ],
  {
    cwd: root,
    stdio: "inherit",
    env: process.env,
  },
);

process.exit(result.status ?? 1);
