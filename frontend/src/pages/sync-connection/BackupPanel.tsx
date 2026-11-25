import { ChangeEvent, useRef } from "react";
import {
  CheckCircle2,
  Download,
  HardDrive,
  HardDriveUpload,
  LoaderCircle,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";

interface Props {
  autoBackupStatus: string;
  lastBackupTime: string | null;
  lastBackupStatus: string;
  serverActionsAvailable: boolean;
  operationState: string;
  canDownloadBackup: boolean;
  canRestoreBackup: boolean;
  selectedFileName: string | null;
  selectedFileSizeLabel: string | null;
  restoreWarning: string | null;
  downloadLoading: boolean;
  restoreLoading: boolean;
  onPickRestoreFile: (file: File | null) => void;
  onDownloadBackup: () => Promise<void>;
  onRestoreBackup: () => Promise<void>;
}

export const BackupPanel = ({
  autoBackupStatus,
  lastBackupTime,
  lastBackupStatus,
  serverActionsAvailable,
  operationState,
  canDownloadBackup,
  canRestoreBackup,
  selectedFileName,
  selectedFileSizeLabel,
  restoreWarning,
  downloadLoading,
  restoreLoading,
  onPickRestoreFile,
  onDownloadBackup,
  onRestoreBackup,
}: Props) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const isBackupActive = autoBackupStatus.toLowerCase().includes("active");
  const operationRunning =
    downloadLoading ||
    restoreLoading ||
    !["IDLE", "COMPLETED", "FAILED", "idle", "completed", "failed"].includes(operationState);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    onPickRestoreFile(event.target.files?.[0] || null);
  };

  return (
    <Card className="overflow-hidden rounded-[1.75rem] border-slate-200 bg-white p-0 shadow-sm">
      <div className="relative overflow-hidden border-b border-slate-200 bg-slate-950 px-5 py-6 sm:px-6">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(14,165,233,0.18),transparent_38%),radial-gradient(circle_at_bottom_left,rgba(16,185,129,0.14),transparent_34%)]" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/10 text-sky-300 backdrop-blur">
              <HardDrive className="h-5 w-5" />
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-xl font-black tracking-tight text-white">Sauvegardes systeme</h3>
                <span
                  className={[
                    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-bold",
                    isBackupActive
                      ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300"
                      : "border-amber-400/20 bg-amber-400/10 text-amber-300",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "h-1.5 w-1.5 rounded-full",
                      isBackupActive ? "bg-emerald-400" : "bg-amber-400",
                    ].join(" ")}
                  />
                  {autoBackupStatus}
                </span>
              </div>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                Telechargez une sauvegarde complete de PostgreSQL ou importez un fichier pour
                restaurer la base du serveur.
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.06] px-4 py-3 backdrop-blur">
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">
              Etat courant
            </p>
            <p className="mt-1 text-base font-black text-white">{operationState || "IDLE"}</p>
          </div>
        </div>
      </div>

      <div className="space-y-6 p-5 sm:p-6">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                Sauvegarde auto
              </p>
              <ShieldCheck
                className={[
                  "h-4 w-4",
                  isBackupActive ? "text-emerald-600" : "text-amber-600",
                ].join(" ")}
              />
            </div>
            <p className="mt-3 text-sm font-bold text-slate-950">{autoBackupStatus}</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                Derniere sauvegarde
              </p>
              <CheckCircle2 className="h-4 w-4 text-sky-600" />
            </div>
            <p className="mt-3 text-sm font-bold text-slate-950">{lastBackupTime || "Aucune sauvegarde"}</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                Execution
              </p>
              <LoaderCircle className={`h-4 w-4 text-violet-600 ${operationRunning ? "animate-spin" : ""}`} />
            </div>
            <p className="mt-3 text-sm font-bold text-slate-950">
              {serverActionsAvailable ? "Poste serveur actif" : "Poste client"}
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">Dernier etat</p>
          <p className="mt-2 text-sm font-bold text-slate-950">{lastBackupStatus || "Statut indisponible"}</p>
        </div>

        {!serverActionsAvailable ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm font-semibold leading-6 text-amber-900">
            Les sauvegardes PostgreSQL du serveur sont disponibles uniquement sur le poste configure comme serveur.
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
            <div className="flex items-start gap-3">
              <div className="rounded-2xl bg-sky-100 p-3 text-sky-700">
                <Download className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-base font-black text-slate-950">Telecharger une sauvegarde complete</h4>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Cree et telecharge une copie complete de toutes les donnees de la base PostgreSQL.
                </p>
              </div>
            </div>

            <Button
              icon={Download}
              loading={downloadLoading}
              disabled={operationRunning || !canDownloadBackup}
              className="mt-5 w-full justify-center"
              onClick={() => void onDownloadBackup()}
            >
              {downloadLoading ? "Creation de la sauvegarde..." : "Telecharger une sauvegarde complete"}
            </Button>
          </div>

          <div className="rounded-[1.5rem] border border-amber-200 bg-amber-50/70 p-5">
            <div className="flex items-start gap-3">
              <div className="rounded-2xl bg-amber-100 p-3 text-amber-700">
                <HardDriveUpload className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-base font-black text-slate-950">Importer et restaurer une sauvegarde</h4>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Restaure une sauvegarde complete dans la base PostgreSQL de ce serveur.
                </p>
              </div>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".backup,.dump"
              className="hidden"
              onChange={handleFileChange}
            />

            <Button
              variant="secondary"
              icon={HardDriveUpload}
              disabled={operationRunning || !serverActionsAvailable}
              className="mt-5 w-full justify-center"
              onClick={() => fileInputRef.current?.click()}
            >
              Choisir un fichier de sauvegarde
            </Button>

            <div className="mt-4 rounded-2xl border border-amber-200 bg-white px-4 py-3">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Fichier selectionne</p>
              <p className="mt-2 text-sm font-bold text-slate-950">{selectedFileName || "Aucun fichier selectionne"}</p>
              <p className="mt-1 text-xs text-slate-500">{selectedFileSizeLabel || "Formats acceptes: .backup, .dump"}</p>
            </div>

            <div
              className={[
                "mt-4 flex items-start gap-3 rounded-2xl px-4 py-3 text-sm",
                restoreWarning
                  ? "border border-rose-200 bg-rose-50 text-rose-800"
                  : "border border-amber-200 bg-amber-100/70 text-amber-900",
              ].join(" ")}
            >
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                {restoreWarning ||
                  "Une sauvegarde automatique de l'etat actuel sera creee avant la restauration."}
              </p>
            </div>

            <Button
              icon={HardDriveUpload}
              loading={restoreLoading}
              disabled={operationRunning || !canRestoreBackup}
              className="mt-5 w-full justify-center"
              onClick={() => void onRestoreBackup()}
            >
              {restoreLoading ? "Restauration de la base PostgreSQL en cours..." : "Importer et restaurer une sauvegarde"}
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
};
