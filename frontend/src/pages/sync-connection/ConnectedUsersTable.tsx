import {
  Laptop,
  MonitorSmartphone,
  Network,
  Radio,
  UserRound,
  Users,
} from "lucide-react";

import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";

export type ConnectedUserRow = {
  name: string;
  role: string;
  device_name: string;
  ip_address: string;
  last_seen: string | null;
  status: string;
  connected_since?: string | null;
  app_version?: string | null;
  operating_system?: string | null;
  latency_ms?: number | null;
  pending_operations_count?: number;
};

interface Props {
  users: ConnectedUserRow[];
}

const statusLabelMap = (value: string) => {
  const normalized = value.toLowerCase();

  if (normalized.includes("offline")) {
    return {
      label: "Hors ligne",
      tone: "inactive",
      dotClassName: "bg-slate-400",
    };
  }

  if (normalized.includes("inactive")) {
    return {
      label: "Inactif",
      tone: "pending",
      dotClassName: "bg-amber-500",
    };
  }

  if (
    normalized.includes("online") ||
    normalized.includes("connected") ||
    normalized.includes("server")
  ) {
    return {
      label: "En ligne",
      tone: "active",
      dotClassName: "bg-emerald-500",
    };
  }

  return {
    label: value || "Inconnu",
    tone: "pending",
    dotClassName: "bg-amber-500",
  };
};

const initialsFromName = (name: string) => {
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");

  return initials || "U";
};

export const ConnectedUsersTable = ({ users }: Props) => {
  const onlineUsers = users.filter((user) => {
    const normalized = user.status.toLowerCase();

    return (
      normalized.includes("online") ||
      normalized.includes("connected") ||
      normalized.includes("server")
    );
  }).length;

  const inactiveUsers = users.filter((user) =>
    user.status.toLowerCase().includes("inactive"),
  ).length;

  return (
    <Card className="overflow-hidden rounded-[1.75rem] border-slate-200 bg-white p-0 shadow-sm">
      <div className="relative overflow-hidden border-b border-slate-200 bg-slate-950 px-5 py-6 sm:px-6">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(14,165,233,0.2),transparent_38%),radial-gradient(circle_at_bottom_left,rgba(16,185,129,0.12),transparent_34%)]" />

        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/10 text-sky-300 backdrop-blur">
              <Users className="h-5 w-5" />
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-xl font-black tracking-tight text-white">
                  Postes connectés
                </h3>

                <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-400/20 bg-sky-400/10 px-2.5 py-1 text-[11px] font-bold text-sky-300">
                  <Radio className="h-3.5 w-3.5" />
                  Surveillance en direct
                </span>
              </div>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                Suivez les utilisateurs actifs, leurs rôles, leurs postes, leurs adresses IP et
                leur dernière activité sur le réseau local.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 sm:min-w-[320px]">
            {[
              { label: "Total", value: users.length, icon: MonitorSmartphone },
              { label: "En ligne", value: onlineUsers, icon: Network },
              { label: "Inactifs", value: inactiveUsers, icon: Laptop },
            ].map((item) => {
              const Icon = item.icon;

              return (
                <div
                  key={item.label}
                  className="rounded-2xl border border-white/10 bg-white/[0.06] p-3 backdrop-blur"
                >
                  <Icon className="h-4 w-4 text-sky-300" />
                  <p className="mt-2 text-[10px] font-black uppercase tracking-[0.14em] text-slate-400">
                    {item.label}
                  </p>
                  <p className="mt-1 text-lg font-black text-white">{item.value}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
          <thead>
            <tr className="bg-slate-50/90 text-slate-500">
              {[
                "Utilisateur",
                "Rôle",
                "Poste",
                "Adresse IP",
                "Dernière activité",
                "État",
              ].map((heading) => (
                <th
                  key={heading}
                  className="border-b border-slate-200 px-6 py-4 text-[11px] font-black uppercase tracking-[0.15em]"
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {users.length ? (
              users.map((user) => {
                const badge = statusLabelMap(user.status);

                return (
                  <tr
                    key={`${user.name}-${user.device_name}-${user.ip_address}`}
                    className="group transition-colors hover:bg-sky-50/40"
                  >
                    <td className="border-b border-slate-100 px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-xs font-black text-slate-700 transition group-hover:bg-sky-100 group-hover:text-sky-700">
                          {initialsFromName(user.name)}
                        </div>

                        <div className="min-w-0">
                          <p className="truncate font-bold text-slate-950">{user.name}</p>
                          <p className="mt-0.5 text-xs text-slate-500">{user.device_name}</p>
                        </div>
                      </div>
                    </td>

                    <td className="border-b border-slate-100 px-6 py-4">
                      <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700">
                        {user.role}
                      </span>
                    </td>

                    <td className="border-b border-slate-100 px-6 py-4 text-sm font-medium text-slate-600">
                      {user.device_name}
                    </td>

                    <td className="border-b border-slate-100 px-6 py-4">
                      <code className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs font-bold text-slate-700">
                        {user.ip_address}
                      </code>
                    </td>

                    <td className="border-b border-slate-100 px-6 py-4 text-sm text-slate-600">
                      {user.last_seen || "-"}
                    </td>

                    <td className="border-b border-slate-100 px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${badge.dotClassName}`} />
                        <Badge tone={badge.tone}>{badge.label}</Badge>
                      </div>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={6} className="px-6 py-14">
                  <div className="text-center">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
                      <MonitorSmartphone className="h-5 w-5" />
                    </div>
                    <p className="mt-4 text-sm font-bold text-slate-700">Aucun poste connecté</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Les postes clients apparaîtront ici après leur connexion au serveur.
                    </p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="space-y-3 p-4 md:hidden">
        {users.length ? (
          users.map((user) => {
            const badge = statusLabelMap(user.status);

            return (
              <article
                key={`${user.name}-${user.device_name}-${user.ip_address}`}
                className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white text-xs font-black text-slate-700 shadow-sm">
                      {initialsFromName(user.name)}
                    </div>

                    <div className="min-w-0">
                      <p className="truncate text-sm font-black text-slate-950">{user.name}</p>
                      <p className="mt-0.5 text-xs text-slate-500">{user.role}</p>
                    </div>
                  </div>

                  <Badge tone={badge.tone}>{badge.label}</Badge>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-3">
                    <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
                      Poste
                    </p>
                    <p className="mt-1.5 text-sm font-semibold text-slate-900">{user.device_name}</p>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-3">
                    <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
                      Adresse IP
                    </p>
                    <p className="mt-1.5 break-all text-sm font-semibold text-slate-900">
                      {user.ip_address}
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 sm:col-span-2">
                    <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
                      Dernière activité
                    </p>
                    <p className="mt-1.5 text-sm font-semibold text-slate-900">
                      {user.last_seen || "-"}
                    </p>
                  </div>
                </div>
              </article>
            );
          })
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center">
            <UserRound className="mx-auto h-6 w-6 text-slate-400" />
            <p className="mt-3 text-sm font-bold text-slate-700">Aucun poste connecté</p>
            <p className="mt-1 text-xs text-slate-500">
              Les postes apparaîtront après leur connexion.
            </p>
          </div>
        )}
      </div>
    </Card>
  );
};
