import { useCallback, useMemo } from "react";
import { Navigate } from "react-router-dom";
import { auditApi } from "@/api/auditApi";
import { EmptyState } from "@/components/common/EmptyState";
import { Pagination } from "@/components/common/Pagination";
import { SearchInput } from "@/components/common/SearchInput";
import { SectionHeader } from "@/components/common/SectionHeader";
import { useAuth } from "@/hooks/useAuth";
import { usePaginatedResource } from "@/hooks/usePaginatedResource";
import type { AuditLog } from "@/types/entities";
import type { DashboardAuditItem } from "@/types/dashboard";
import { mockAuditLogs } from "@/utils/mockData";
import { hasRole } from "@/utils/permissions";
import { AuditActivityList } from "@/pages/dashboard/components/AdminDashboardWidgets";

export const AuditLogsPage = () => {
  const { user } = useAuth();
  const { items, total, page, pageSize, search, loading, error, setPage, setSearch } =
    usePaginatedResource<AuditLog>(useCallback(auditApi.list, []), mockAuditLogs);

  const auditItems = useMemo<DashboardAuditItem[]>(
    () =>
      items.map((item) => ({
        id: item.id,
        action: item.action,
        actor_name: item.actor_name || item.actor_email || null,
        actor_email: item.actor_email,
        actor_role: item.actor_role,
        entity_type: item.entity_type,
        entity_id: item.entity_id,
        entity_name: item.entity_name || item.description || null,
        ip_address: item.ip_address,
        details_summary: item.details_summary || item.description || null,
        created_at: item.created_at,
      })),
    [items],
  );

  if (!hasRole(user, ["Super Admin", "Admin"])) {
    return <Navigate to="/404" replace />;
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Governance"
        title="Journal d'audit"
        description={error || "Consultez le journal d'activité complet avec les actions, les entités, les utilisateurs et les détails d'audit."}
      />
      <SearchInput value={search} onChange={setSearch} placeholder="Rechercher dans le journal d'audit..." />
      {loading ? (
        <div className="rounded-[1.8rem] border border-slate-200 bg-white px-6 py-14 text-center shadow-xl shadow-slate-950/[0.03]">
          <p className="text-sm font-medium text-slate-500">Chargement du journal d'activité...</p>
        </div>
      ) : auditItems.length === 0 ? (
        <EmptyState
          title="Aucune activité trouvée"
          description="Aucun événement d'audit ne correspond aux filtres actuels."
        />
      ) : (
        <AuditActivityList items={auditItems} />
      )}
      <Pagination page={page} total={total} pageSize={pageSize} onPageChange={setPage} />
    </div>
  );
};
