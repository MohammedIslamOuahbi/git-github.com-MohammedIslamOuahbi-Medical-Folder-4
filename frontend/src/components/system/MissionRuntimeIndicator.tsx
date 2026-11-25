import { AlertTriangle, ArrowUpRight, Laptop2, Server, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/common/Badge";
import type { RuntimeStatus } from "@/types/mission";

const modeCopy = (runtime: RuntimeStatus) => {
  if (runtime.runtimeMode === "mission_server") {
    return {
      label: `Serveur de mission - ${runtime.activeMission?.code || "Mission active"}`,
      icon: Server,
    };
  }
  if (runtime.runtimeMode === "mission_client") {
    return {
      label: `Client de mission - connecte a ${runtime.missionServerName || runtime.device?.device_code || "serveur"}`,
      icon: Laptop2,
    };
  }
  return {
    label: `Mode autonome - ${runtime.device?.device_code || "poste local"}`,
    icon: ShieldCheck,
  };
};

export const MissionRuntimeIndicator = ({
  runtime,
  compact = false,
}: {
  runtime: RuntimeStatus;
  compact?: boolean;
}) => {
  const navigate = useNavigate();
  const mode = modeCopy(runtime);
  const Icon = mode.icon;
  const isDisconnected = runtime.runtimeMode === "mission_client" && runtime.connectionState === "disconnected";

  return (
    <button
      type="button"
      onClick={() => navigate("/sync/mission")}
      className={[
        "inline-flex items-center gap-2 rounded-2xl border px-3 py-2 text-left transition-all duration-200 hover:-translate-y-0.5",
        isDisconnected
          ? "border-rose-200 bg-rose-50 text-rose-800"
          : "border-slate-200 bg-white text-slate-800",
        compact ? "max-w-[420px]" : "w-full justify-between",
      ].join(" ")}
    >
      <span className="inline-flex items-center gap-2 min-w-0">
        <span
          className={[
            "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
            isDisconnected ? "bg-rose-100 text-rose-700" : "bg-sky-50 text-sky-700",
          ].join(" ")}
        >
          {isDisconnected ? <AlertTriangle className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-xs font-black uppercase tracking-[0.14em] text-slate-500">
            Infrastructure mission
          </span>
          <span className="block truncate text-sm font-bold">{mode.label}</span>
        </span>
      </span>

      <span className="inline-flex items-center gap-2 shrink-0">
        <Badge tone={isDisconnected ? "failed" : runtime.connectionState === "connected" ? "active" : "pending"}>
          {isDisconnected ? "Deconnecte" : runtime.connectionState}
        </Badge>
        <ArrowUpRight className="h-4 w-4 text-slate-400" />
      </span>
    </button>
  );
};
