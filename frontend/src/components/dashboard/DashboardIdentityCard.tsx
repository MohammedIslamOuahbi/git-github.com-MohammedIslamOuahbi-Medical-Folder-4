import { IdCard, KeyRound, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { Card } from "@/components/common/Card";
import { Badge } from "@/components/common/Badge";
import { useAuth } from "@/hooks/useAuth";
import { buildUserDashboardUid } from "@/utils/uid";

export const DashboardIdentityCard = () => {
  const { user } = useAuth();

  if (!user) return null;

  const dashboardUid = buildUserDashboardUid(user);
  const permissionCount = user.permissions?.length || 0;
  const accessScope =
    user.role === "Admin"
      ? "Accès complet au système"
      : user.role === "Doctor"
        ? "Accès clinique"
        : "Accès opérationnel";

  return (
    <Card className="bg-gradient-to-r from-white to-brand-50/50">
      <div className="flex items-start justify-between gap-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
              <IdCard className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-xl font-semibold text-navy-900">
                {user.full_name || `${user.first_name} ${user.last_name}`.trim()}
              </h3>
              <p className="mt-1 text-sm text-ink-500">
                Accès au tableau de bord personnel et vue d'ensemble du compte.
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="active">{user.role}</Badge>
          <Badge tone="reviewed">{dashboardUid}</Badge>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-4 gap-3">
        <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink-400">
            <Mail className="h-3.5 w-3.5" />
            E-mail
          </div>
          <p className="mt-2 text-sm font-medium text-navy-900">{user.email}</p>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink-400">
            <ShieldCheck className="h-3.5 w-3.5" />
            Rôle
          </div>
          <p className="mt-2 text-sm font-medium text-navy-900">{user.role}</p>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink-400">
            <Sparkles className="h-3.5 w-3.5" />
            Portée d'accès
          </div>
          <p className="mt-2 text-sm font-medium text-navy-900">{accessScope}</p>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/70 px-4 py-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink-400">
            <KeyRound className="h-3.5 w-3.5" />
            Autorisations
          </div>
          <p className="mt-2 text-sm font-medium text-navy-900">
            {permissionCount ? `${permissionCount} attribuées` : "Héritées du rôle"}
          </p>
        </div>
      </div>
    </Card>
  );
};
