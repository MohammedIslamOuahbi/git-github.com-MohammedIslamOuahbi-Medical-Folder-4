import { Badge } from "@/components/common/Badge";

const labelMap: Record<string, { label: string; tone: string }> = {
  local_only: { label: "Local uniquement", tone: "inactive" },
  mission_recorded: { label: "Enregistre dans la mission", tone: "completed" },
  copied_local: { label: "Copie localement", tone: "completed" },
  never_submitted: { label: "Jamais envoyee", tone: "inactive" },
  central_pending: { label: "En attente du serveur central", tone: "pending" },
  central_accepted: { label: "Accepte par le serveur central", tone: "completed" },
  central_conflict: { label: "Conflit central", tone: "failed" },
  central_rejected: { label: "Rejete", tone: "failed" },
  central_finalized: { label: "Finalise centralement", tone: "active" },
};

export const resolveCentralEntityStatus = (
  centralSyncStatus?: string | null,
  missionUuid?: string | null,
) => {
  if (centralSyncStatus && labelMap[centralSyncStatus]) {
    return labelMap[centralSyncStatus];
  }
  if (centralSyncStatus === "central_pending") {
    return labelMap.central_pending;
  }
  if (missionUuid) {
    return labelMap.mission_recorded;
  }
  return labelMap.local_only;
};

export const CentralEntityStatusBadge = ({
  centralSyncStatus,
  missionUuid,
}: {
  centralSyncStatus?: string | null;
  missionUuid?: string | null;
}) => {
  const resolved = resolveCentralEntityStatus(centralSyncStatus, missionUuid);
  return <Badge tone={resolved.tone}>{resolved.label}</Badge>;
};
