// Lance l'API FastAPI avec le Python du venv du projet (Windows ou Linux/macOS).
// Utilisé par `npm run api` et `npm run dev:all`.
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const candidates = [
  join(root, ".venv", "Scripts", "python.exe"),
  join(root, ".venv", "bin", "python"),
];
const python = candidates.find((p) => existsSync(p));
if (!python) {
  console.error("Python du venv introuvable : créer .venv à la racine du projet (voir README).");
  process.exit(1);
}
const child = spawn(
  python,
  ["-m", "uvicorn", "api.main:app", "--reload", "--port", "8000"],
  { cwd: root, stdio: "inherit" },
);
// Arrêt de tout l'arbre : sous Windows, le rechargeur d'uvicorn lance un processus « worker »
// qui survivrait (et garderait le port 8000) si l'on ne tuait que le processus principal.
function stopTree() {
  if (child.exitCode !== null) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    child.kill("SIGTERM");
  }
}
child.on("exit", (code) => process.exit(code ?? 0));
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => {
    stopTree();
    process.exit(0);
  });
}
process.on("exit", stopTree);
