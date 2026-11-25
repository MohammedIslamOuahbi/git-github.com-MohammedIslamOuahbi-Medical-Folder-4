import { useState } from "react";
import {
  Activity,
  CheckCircle2,
  Database,
  Globe2,
  PlayCircle,
  Power,
  RefreshCw,
  Server,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";

interface Props {
  serverName: string;
  localIp: string;
  backendUrl: string;
  port: string;
  serverStatus: string;
  currentMode: string;
  userRole: string;
  postgresqlStatus: string;
  showControls?: boolean;
  onStart: () => Promise<void>;
  onStop: () => Promise<void>;
  onTest: () => Promise<void>;
}

const toneFromStatus = (value: string) => {
  const normalized = value.toLowerCase();

  if (
    normalized.includes("running") ||
    normalized.includes("connect") ||
    normalized.includes("server")
  ) {
    return "active";
  }

  if (normalized.includes("offline") || normalized.includes("stop")) {
    return "failed";
  }

  return "pending";
};

const isServerRunning = (value: string) => {
  const normalized = value.toLowerCase();

  return (
    normalized.includes("running") ||
    normalized.includes("connect") ||
    normalized.includes("server")
  );
};

export const ServerModePanel = ({
  serverName,
  localIp,
  backendUrl,
  port,
  serverStatus,
  currentMode,
  userRole,
  postgresqlStatus,
  showControls = true,
  onStart,
  onStop,
  onTest,
}: Props) => {
  const [loading, setLoading] = useState<"start" | "stop" | "test" | null>(null);
  const running = isServerRunning(serverStatus);

  return (
    <Card className="overflow-hidden rounded-[1.75rem] border-slate-200 bg-white p-0 shadow-sm">
      <div className="relative overflow-hidden border-b border-slate-200 bg-slate-950 px-5 py-6 sm:px-6">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(14,165,233,0.2),transparent_38%),radial-gradient(circle_at_bottom_left,rgba(16,185,129,0.14),transparent_34%)]" />

        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/10 text-sky-300 backdrop-blur">
              <Server className="h-5 w-5" />
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-xl font-black tracking-tight text-white">
                  Serveur principal
                </h3>

                <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-400/20 bg-sky-400/10 px-2.5 py-1 text-[11px] font-bold text-sky-300">
                  <Activity className="h-3.5 w-3.5" />
                  {currentMode}
                </span>
              </div>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                Administrez le backend FastAPI, PostgreSQL et l’accès réseau des postes clients
                depuis ce serveur.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge tone={toneFromStatus(serverStatus)}>{serverStatus}</Badge>
            <Badge tone="reviewed">{userRole}</Badge>
          </div>
        </div>
      </div>

      <div className="space-y-6 p-5 sm:p-6">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: "Nom du serveur",
              value: serverName,
              icon: Server,
              iconClassName: "bg-sky-50 text-sky-700",
            },
            {
              label: "Adresse IP locale",
              value: localIp,
              icon: Globe2,
              iconClassName: "bg-cyan-50 text-cyan-700",
            },
            {
              label: "Port API",
              value: port,
              icon: ShieldCheck,
              iconClassName: "bg-violet-50 text-violet-700",
            },
            {
              label: "PostgreSQL",
              value: postgresqlStatus,
              icon: Database,
              iconClassName: "bg-emerald-50 text-emerald-700",
            },
          ].map((item) => {
            const Icon = item.icon;

            return (
              <div
                key={item.label}
                className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                      {item.label}
                    </p>
                    <p className="mt-3 break-words text-sm font-bold text-slate-950">
                      {item.value}
                    </p>
                  </div>

                  <div className={`rounded-xl p-2.5 ${item.iconClassName}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.35fr_0.65fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-sky-600" />
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                URL du backend
              </p>
            </div>

            <code className="mt-3 block break-all rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs font-bold leading-5 text-slate-800">
              {backendUrl}
            </code>
          </div>

          <div
            className={[
              "rounded-2xl border p-5",
              running
                ? "border-emerald-200 bg-emerald-50"
                : "border-amber-200 bg-amber-50",
            ].join(" ")}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p
                  className={[
                    "text-[11px] font-black uppercase tracking-[0.14em]",
                    running ? "text-emerald-700" : "text-amber-700",
                  ].join(" ")}
                >
                  État du serveur
                </p>

                <p
                  className={[
                    "mt-3 text-base font-black",
                    running ? "text-emerald-950" : "text-amber-950",
                  ].join(" ")}
                >
                  {serverStatus}
                </p>

                <p
                  className={[
                    "mt-1 text-xs leading-5",
                    running ? "text-emerald-700" : "text-amber-700",
                  ].join(" ")}
                >
                  {running
                    ? "Le backend est prêt à recevoir les postes clients."
                    : "Démarrez ou testez le serveur avant utilisation."}
                </p>
              </div>

              <div
                className={[
                  "rounded-2xl p-3",
                  running
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-amber-100 text-amber-700",
                ].join(" ")}
              >
                {running ? (
                  <CheckCircle2 className="h-5 w-5" />
                ) : (
                  <Power className="h-5 w-5" />
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="flex items-center gap-2">
            <Stethoscope className="h-4 w-4 text-slate-600" />
            <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
              Session administrateur
            </p>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold capitalize text-slate-950">{userRole}</p>
              <p className="mt-1 text-xs text-slate-500">
                Autorisations serveur appliquées selon le rôle connecté.
              </p>
            </div>

            <Badge tone={showControls ? "active" : "inactive"}>
              {showControls ? "Contrôle autorisé" : "Lecture seule"}
            </Badge>
          </div>
        </div>

        {showControls ? (
          <div className="border-t border-slate-200 pt-5">
            <div className="mb-4">
              <h4 className="text-sm font-black text-slate-950">
                Contrôles du serveur
              </h4>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Démarrez, arrêtez ou testez le backend. Une seule action peut être exécutée à la fois.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <Button
                icon={PlayCircle}
                loading={loading === "start"}
                disabled={loading !== null && loading !== "start"}
                className="w-full justify-center"
                onClick={async () => {
                  setLoading("start");
                  try {
                    await onStart();
                  } finally {
                    setLoading(null);
                  }
                }}
              >
                Démarrer le serveur
              </Button>

              <Button
                variant="secondary"
                icon={Power}
                loading={loading === "stop"}
                disabled={loading !== null && loading !== "stop"}
                className="w-full justify-center"
                onClick={async () => {
                  setLoading("stop");
                  try {
                    await onStop();
                  } finally {
                    setLoading(null);
                  }
                }}
              >
                Arrêter le serveur
              </Button>

              <Button
                variant="ghost"
                icon={RefreshCw}
                loading={loading === "test"}
                disabled={loading !== null && loading !== "test"}
                className="w-full justify-center"
                onClick={async () => {
                  setLoading("test");
                  try {
                    await onTest();
                  } finally {
                    setLoading(null);
                  }
                }}
              >
                Tester le serveur
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  );
};