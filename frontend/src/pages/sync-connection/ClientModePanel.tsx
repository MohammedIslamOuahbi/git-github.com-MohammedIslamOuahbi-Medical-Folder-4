import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Laptop,
  Link2,
  Plug2,
  RefreshCw,
  Server,
  ShieldAlert,
  Wifi,
} from "lucide-react";

import { Input } from "@/components/common/Input";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";

interface Props {
  serverUrl: string;
  connectionStatus: string;
  serverReachability: string;
  warningMessage?: string | null;
  onServerUrlChange: (value: string) => void;
  onConnect: () => Promise<void>;
  onDisconnect: () => Promise<void>;
  onTest: () => Promise<void>;
}

const toneFromReachability = (value: string) => {
  const normalized = value.toLowerCase();

  if (normalized.includes("connect") || normalized.includes("accessible")) {
    return "active";
  }

  if (normalized.includes("erreur") || normalized.includes("inaccessible")) {
    return "failed";
  }

  return "pending";
};

const isReachable = (value: string) => {
  const normalized = value.toLowerCase();
  return normalized.includes("connect") || normalized.includes("accessible");
};

export const ClientModePanel = ({
  serverUrl,
  connectionStatus,
  serverReachability,
  warningMessage,
  onServerUrlChange,
  onConnect,
  onDisconnect,
  onTest,
}: Props) => {
  const [loading, setLoading] = useState<"test" | "connect" | "disconnect" | null>(null);
  const reachable = isReachable(serverReachability);

  return (
    <Card className="overflow-hidden rounded-[1.75rem] border-slate-200 bg-white p-0 shadow-sm">
      <div className="relative overflow-hidden border-b border-slate-200 bg-slate-950 px-5 py-6 sm:px-6">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(14,165,233,0.2),transparent_38%),radial-gradient(circle_at_bottom_left,rgba(59,130,246,0.14),transparent_34%)]" />

        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/10 text-sky-300 backdrop-blur">
              <Laptop className="h-5 w-5" />
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-xl font-black tracking-tight text-white">Mode client</h3>

                <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-400/20 bg-sky-400/10 px-2.5 py-1 text-[11px] font-bold text-sky-300">
                  <Wifi className="h-3.5 w-3.5" />
                  Poste réseau
                </span>
              </div>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                Configurez l’URL API du serveur principal, vérifiez son accessibilité et connectez
                ce poste au réseau local de la clinique.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge tone={toneFromReachability(connectionStatus)}>{connectionStatus}</Badge>
            <Badge tone={toneFromReachability(serverReachability)}>{serverReachability}</Badge>
          </div>
        </div>
      </div>

      <div className="space-y-6 p-5 sm:p-6">
        <div className="grid gap-4 lg:grid-cols-[1.35fr_0.65fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <Server className="h-4 w-4 text-sky-600" />
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                Configuration du serveur
              </p>
            </div>

            <Input
              label="URL API du serveur"
              value={serverUrl}
              onChange={(event) => onServerUrlChange(event.target.value)}
              placeholder="http://192.168.0.136:8000"
            />

            <div className="mt-3 flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-3">
              <Link2 className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
              <p className="break-all text-xs leading-5 text-slate-600">
                {serverUrl || "Aucune URL serveur configurée"}
              </p>
            </div>
          </div>

          <div
            className={[
              "rounded-2xl border p-5",
              reachable
                ? "border-emerald-200 bg-emerald-50"
                : "border-amber-200 bg-amber-50",
            ].join(" ")}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p
                  className={[
                    "text-[11px] font-black uppercase tracking-[0.14em]",
                    reachable ? "text-emerald-700" : "text-amber-700",
                  ].join(" ")}
                >
                  État du serveur
                </p>

                <p
                  className={[
                    "mt-3 text-base font-black",
                    reachable ? "text-emerald-950" : "text-amber-950",
                  ].join(" ")}
                >
                  {serverReachability}
                </p>

                <p
                  className={[
                    "mt-1 text-xs leading-5",
                    reachable ? "text-emerald-700" : "text-amber-700",
                  ].join(" ")}
                >
                  {reachable
                    ? "Le serveur répond correctement."
                    : "Testez l’URL avant de vous connecter."}
                </p>
              </div>

              <div
                className={[
                  "rounded-2xl p-3",
                  reachable
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-amber-100 text-amber-700",
                ].join(" ")}
              >
                {reachable ? (
                  <CheckCircle2 className="h-5 w-5" />
                ) : (
                  <AlertTriangle className="h-5 w-5" />
                )}
              </div>
            </div>
          </div>
        </div>

        {warningMessage ? (
          <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-bold">Configuration requise</p>
              <p className="mt-1 leading-6">{warningMessage}</p>
            </div>
          </div>
        ) : null}

        <div className="border-t border-slate-200 pt-5">
          <div className="mb-4">
            <h4 className="text-sm font-black text-slate-950">Actions de connexion</h4>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Testez d’abord l’accès au serveur, puis connectez ou déconnectez ce poste.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
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
              Tester la connexion
            </Button>

            <Button
              icon={Plug2}
              loading={loading === "connect"}
              disabled={loading !== null && loading !== "connect"}
              className="w-full justify-center"
              onClick={async () => {
                setLoading("connect");
                try {
                  await onConnect();
                } finally {
                  setLoading(null);
                }
              }}
            >
              Connecter
            </Button>

            <Button
              variant="secondary"
              icon={ShieldAlert}
              loading={loading === "disconnect"}
              disabled={loading !== null && loading !== "disconnect"}
              className="w-full justify-center"
              onClick={async () => {
                setLoading("disconnect");
                try {
                  await onDisconnect();
                } finally {
                  setLoading(null);
                }
              }}
            >
              Déconnecter
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
};