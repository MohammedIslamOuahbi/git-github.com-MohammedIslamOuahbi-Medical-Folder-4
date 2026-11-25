import { Navigate } from "react-router-dom";

import { Card } from "@/components/common/Card";
import { MOBILE_HOME_ROUTE } from "@/features/mobile/mobileDeviceFlow";
import { useMissionSubmissions } from "@/hooks/useCentralInstallation";
import { useInstallationProfile } from "@/hooks/useInstallationProfile";

export const CentralMissionSubmissionsPage = () => {
  const { isCentralServer } = useInstallationProfile();
  const { data: submissions } = useMissionSubmissions(isCentralServer);

  if (!isCentralServer) {
    return <Navigate to={MOBILE_HOME_ROUTE} replace />;
  }

  return (
    <Card className="rounded-[2rem] p-6">
      <h1 className="text-2xl font-black text-slate-950">Missions reçues</h1>
      <p className="mt-2 text-sm text-slate-600">Code mission, poste source, séquence finale, changements et statut.</p>
      <div className="mt-5 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-[0.14em] text-slate-500">
            <tr>
              <th className="pb-3">Mission</th>
              <th className="pb-3">Poste mission</th>
              <th className="pb-3">Séquence finale</th>
              <th className="pb-3">Changements</th>
              <th className="pb-3">Acceptés</th>
              <th className="pb-3">Conflits</th>
              <th className="pb-3">Statut</th>
            </tr>
          </thead>
          <tbody>
            {submissions.map((submission) => (
              <tr key={submission.uuid} className="border-t border-slate-100">
                <td className="py-3 font-semibold text-slate-900">{submission.mission_code || "-"}</td>
                <td className="py-3">{submission.mission_server_device || "-"}</td>
                <td className="py-3">{submission.final_mission_sequence ?? "-"}</td>
                <td className="py-3">{submission.submitted_changes}</td>
                <td className="py-3">{submission.accepted}</td>
                <td className="py-3">{submission.conflicts}</td>
                <td className="py-3">{submission.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
