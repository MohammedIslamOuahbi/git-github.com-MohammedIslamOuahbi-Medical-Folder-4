import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const packageJson = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));
const version = packageJson.version;
const nsisDir = path.join(root, "src-tauri", "target", "release", "bundle", "nsis");
const releaseDir = path.join(root, "dist-tauri");

if (!existsSync(nsisDir)) {
  console.error("NSIS bundle output was not found. Run the Tauri build first.");
  process.exit(1);
}

const files = readdirSync(nsisDir);
const installerName = files.find((file) => file.endsWith(".exe"));
if (!installerName) {
  console.error("No NSIS installer .exe was found in the Tauri bundle output.");
  process.exit(1);
}

const sigName = `${installerName}.sig`;
if (!files.includes(sigName)) {
  console.error(`Missing updater signature file: ${sigName}`);
  process.exit(1);
}

const releaseBaseUrl = (process.env.TAURI_RELEASE_BASE_URL || "REPLACE_WITH_RELEASE_URL").replace(/\/+$/, "");
const signature = readFileSync(path.join(nsisDir, sigName), "utf8").trim();
const latestJson = {
  version,
  notes: process.env.TAURI_RELEASE_NOTES || `Desktop release ${version}`,
  pub_date: new Date().toISOString(),
  platforms: {
    "windows-x86_64": {
      signature,
      url: `${releaseBaseUrl}/${installerName}`,
    },
  },
};

mkdirSync(releaseDir, { recursive: true });
copyFileSync(path.join(nsisDir, installerName), path.join(releaseDir, installerName));
copyFileSync(path.join(nsisDir, sigName), path.join(releaseDir, sigName));
writeFileSync(path.join(releaseDir, "latest.json"), `${JSON.stringify(latestJson, null, 2)}\n`, "utf8");

console.log(`Release artifacts written to ${releaseDir}`);

