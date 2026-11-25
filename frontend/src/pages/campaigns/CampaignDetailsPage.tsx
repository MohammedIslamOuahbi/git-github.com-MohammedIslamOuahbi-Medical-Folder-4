import { useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Pencil,
  Stethoscope,
  Users,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { campaignsApi } from "@/api/campaignsApi";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { SectionHeader } from "@/components/common/SectionHeader";
import { DataTable } from "@/components/tables/DataTable";
import type { Campaign, CampaignTestAssignment, Worker } from "@/types/entities";
import { formatDisplayDate } from "@/utils/date";
import { mockCampaigns, mockWorkers } from "@/utils/mockData";

export const CampaignDetailsPage = () => {
  const { campaignId } = useParams();
  const navigate = useNavigate();

  const [campaign, setCampaign] = useState<Campaign | null>(mockCampaigns[0]);
  const [workers, setWorkers] = useState<Worker[]>(mockWorkers);
  const [tests, setTests] = useState<CampaignTestAssignment[]>([]);

  useEffect(() => {
    const id = Number(campaignId);

    void (async () => {
      try {
        const [campaignResponse, workersResponse, testsResponse] = await Promise.all([
          campaignsApi.get(id),
          campaignsApi.workers(id),
          campaignsApi.tests(id),
        ]);

        setCampaign(campaignResponse);
        setWorkers(workersResponse);
        setTests(testsResponse);
      } catch {
        setCampaign(mockCampaigns[0]);
        setWorkers(mockWorkers);
        setTests([]);
      }
    })();
  }, [campaignId]);

  const requiredTestsCount = useMemo(
    () => tests.filter((test) => test.required).length,
    [tests],
  );

  const optionalTestsCount = tests.length - requiredTestsCount;

  return (
    <div className="space-y-6 pb-8">
      <SectionHeader
        eyebrow="Détail de la campagne"
        title={campaign?.name || "Campagne"}
        description="Consultez les travailleurs affectés, les examens médicaux configurés et les principales informations opérationnelles de la campagne."
        actionLabel="Modifier la campagne"
        actionIcon={Pencil}
        onAction={campaignId ? () => navigate(`/campaigns/${campaignId}/edit`) : undefined}
      />

      <section className="overflow-hidden rounded-[2rem] border border-sky-900/40 bg-sky-950 shadow-xl shadow-slate-950/10">
        <div className="relative px-5 py-7 sm:px-7 lg:px-8">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(43, 180, 243, 0.22),transparent_36%),radial-gradient(circle_at_bottom_left,rgba(24, 227, 159, 0.14),transparent_32%)]" />

          <div className="relative flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.16em] text-sky-200">
                <ClipboardList className="h-4 w-4" />
                Suivi opérationnel
              </div>

              <h2 className="mt-4 text-2xl font-black tracking-tight text-white sm:text-3xl">
                {campaign?.name || "Campagne médicale"}
              </h2>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                Vue consolidée de l’état de la campagne, de sa période, des travailleurs affectés
                et des examens médicaux planifiés.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={campaign?.status}>{campaign?.status || "Inconnu"}</Badge>
              <Badge tone="reviewed">
                {formatDisplayDate(campaign?.start_date)} au {formatDisplayDate(campaign?.end_date)}
              </Badge>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "État",
            value: campaign?.status || "Inconnu",
            detail: "Statut actuel de la campagne",
            icon: CheckCircle2,
            iconClassName: "border-emerald-200 bg-emerald-50 text-emerald-700",
          },
          {
            label: "Travailleurs",
            value: String(campaign?.worker_count ?? workers.length),
            detail: "Travailleurs affectés",
            icon: Users,
            iconClassName: "border-sky-200 bg-sky-50 text-sky-700",
          },
          {
            label: "Examens",
            value: String(campaign?.tests_count ?? tests.length),
            detail: `${requiredTestsCount} obligatoire(s)`,
            icon: Stethoscope,
            iconClassName: "border-violet-200 bg-violet-50 text-violet-700",
          },
          {
            label: "Période",
            value: formatDisplayDate(campaign?.start_date),
            detail: `Jusqu’au ${formatDisplayDate(campaign?.end_date)}`,
            icon: CalendarDays,
            iconClassName: "border-amber-200 bg-amber-50 text-amber-700",
          },
        ].map((item) => {
          const Icon = item.icon;

          return (
            <Card
              key={item.label}
              className="group rounded-2xl border-slate-200 bg-white p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-lg"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">
                    {item.label}
                  </p>
                  <p className="mt-3 truncate text-2xl font-black tracking-tight text-slate-950">
                    {item.value}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">{item.detail}</p>
                </div>

                <div className={`rounded-2xl border p-3 ${item.iconClassName}`}>
                  <Icon className="h-5 w-5" />
                </div>
              </div>
            </Card>
          );
        })}
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <Card className="overflow-hidden rounded-[1.75rem] border-slate-200 bg-white p-0 shadow-sm">
          <div className="border-b border-slate-200 px-5 py-5 sm:px-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.14em] text-sky-600">
                  Ressources humaines
                </p>
                <h3 className="mt-2 text-xl font-black text-slate-950">
                  Travailleurs affectés
                </h3>
                <p className="mt-1 text-sm leading-6 text-slate-500">
                  Liste des travailleurs rattachés à cette campagne.
                </p>
              </div>

              <div className="rounded-2xl bg-sky-50 p-3 text-sky-700">
                <Users className="h-5 w-5" />
              </div>
            </div>
          </div>

          <DataTable
            columns={[
              {
                key: "worker",
                title: "Travailleur",
                render: (row: Worker) => row.full_name,
              },
              {
                key: "code",
                title: "Code employé",
                render: (row: Worker) => row.employee_code,
              },
              {
                key: "position",
                title: "Poste",
                render: (row: Worker) => row.position,
              },
            ]}
            data={workers}
            emptyTitle="Aucun travailleur affecté"
            emptyDescription="Les travailleurs de la campagne apparaîtront ici."
            frame="plain"
          />
        </Card>

        <Card className="overflow-hidden rounded-[1.75rem] border-slate-200 bg-white p-0 shadow-sm">
          <div className="border-b border-slate-200 px-5 py-5 sm:px-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.14em] text-violet-600">
                  Configuration médicale
                </p>
                <h3 className="mt-2 text-xl font-black text-slate-950">
                  Examens médicaux
                </h3>
                <p className="mt-1 text-sm leading-6 text-slate-500">
                  Examens obligatoires et optionnels définis pour cette campagne.
                </p>
              </div>

              <div className="rounded-2xl bg-violet-50 p-3 text-violet-700">
                <Stethoscope className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <Badge tone="active">{requiredTestsCount} obligatoire(s)</Badge>
              <Badge tone="inactive">{optionalTestsCount} optionnel(s)</Badge>
            </div>
          </div>

          <DataTable
            columns={[
              {
                key: "test",
                title: "Examen médical",
                render: (row: CampaignTestAssignment) =>
                  row.test?.name || `Test #${row.test_id}`,
              },
              {
                key: "category",
                title: "Catégorie",
                render: (row: CampaignTestAssignment) =>
                  row.test?.section || row.test?.category || "-",
              },
              {
                key: "required",
                title: "Exigence",
                render: (row: CampaignTestAssignment) => (
                  <Badge tone={row.required ? "active" : "inactive"}>
                    {row.required ? "Obligatoire" : "Optionnel"}
                  </Badge>
                ),
              },
            ]}
            data={tests}
            emptyTitle="Aucun examen configuré"
            emptyDescription="Les examens de la campagne apparaîtront ici."
            frame="plain"
          />
        </Card>
      </section>
    </div>
  );
};
