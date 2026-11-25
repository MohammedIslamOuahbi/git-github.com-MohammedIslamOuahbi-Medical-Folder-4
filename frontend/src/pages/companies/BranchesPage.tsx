import { useCallback, useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { branchesApi } from "@/api/branchesApi";
import { Button } from "@/components/common/Button";
import { Input } from "@/components/common/Input";
import { Modal } from "@/components/common/Modal";
import { Pagination } from "@/components/common/Pagination";
import { SearchInput } from "@/components/common/SearchInput";
import { SectionHeader } from "@/components/common/SectionHeader";
import { DataTable } from "@/components/tables/DataTable";
import { usePaginatedResource } from "@/hooks/usePaginatedResource";
import type { Branch } from "@/types/entities";
import { mockBranches } from "@/utils/mockData";

export const BranchesPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { items, total, page, pageSize, search, loading, error, setPage, setSearch, setItems } =
    usePaginatedResource<Branch>(useCallback(branchesApi.list, []), mockBranches);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Partial<Branch>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Branch | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const hasParentCompanyContext = Boolean(form.company_name);

  useEffect(() => {
    if (searchParams.get("action") === "create") {
      const companyId = Number(searchParams.get("company_id") || "");
      const companyName = searchParams.get("company_name") || "";
      setEditingId(null);
      setForm({
        company_id: Number.isFinite(companyId) && companyId > 0 ? companyId : undefined,
        company_name: companyName || undefined,
      });
      setOpen(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const columns = useMemo(
    () => [
      { key: "name", title: "Branch", render: (row: Branch) => row.name },
      { key: "company", title: "Company", render: (row: Branch) => row.company_name || row.company_id },
      { key: "manager", title: "Manager", render: (row: Branch) => row.manager_name || "N/A" },
      { key: "address", title: "Address", render: (row: Branch) => row.address || "N/A" },
      {
        key: "actions",
        title: "Actions",
        render: (row: Branch) => (
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              icon={Pencil}
              onClick={() => {
                setEditingId(row.id);
                setForm(row);
                setOpen(true);
              }}
            >
              Edit
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon={Trash2}
              onClick={() => {
                setDeleteTarget(row);
                setDeletePassword("");
                setDeleteError(null);
              }}
            >
              Delete
            </Button>
          </div>
        ),
      },
    ],
    [setItems],
  );

  const save = async () => {
    try {
      if (editingId) {
        const updated = await branchesApi.update(editingId, form);
        setItems((current) => current.map((item) => (item.id === editingId ? updated : item)));
      } else {
        const created = await branchesApi.create(form);
        setItems((current) => [created, ...current]);
      }
    } catch {
      const localRecord = {
          ...form,
          id: editingId || Date.now(),
          name: form.name || "Offline Branch",
          company_id: Number(form.company_id || 1),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        } as Branch;
      setItems((current) =>
        editingId
          ? current.map((item) => (item.id === editingId ? localRecord : item))
          : [localRecord, ...current],
      );
    } finally {
      setEditingId(null);
      setForm({});
      setOpen(false);
    }
  };

  const removeBranch = async () => {
    if (!deleteTarget) return;
    if (!deletePassword.trim()) {
      setDeleteError("Please enter your password to remove this branch.");
      return;
    }
    try {
      await branchesApi.remove(deleteTarget.id, { password: deletePassword });
    } catch {
      setDeleteError("Unable to remove this branch. Please check your password and try again.");
      return;
    }
    setItems((current) => current.filter((item) => item.id !== deleteTarget.id));
    setDeleteTarget(null);
    setDeletePassword("");
    setDeleteError(null);
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Structure"
        title="Filiales"
        description={error || "Organize company branches, locations, and field operation oversight."}
        actionLabel="New Branch"
        actionIcon={Plus}
        onAction={() => {
          setEditingId(null);
          setForm({});
          setOpen(true);
        }}
      />
      <SearchInput value={search} onChange={setSearch} placeholder="Search branches..." />
      <DataTable columns={columns} data={items} loading={loading} uidScope="branch" />
      <Pagination page={page} total={total} pageSize={pageSize} onPageChange={setPage} />
      <Modal open={open} title={editingId ? "Edit Branch" : "Create Branch"} onClose={() => setOpen(false)}>
        {hasParentCompanyContext ? (
          <div className="mb-4 rounded-2xl border border-brand-100 bg-brand-50/60 px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-700">
              Parent Company
            </p>
            <p className="mt-2 text-sm font-semibold text-navy-900">{form.company_name}</p>
          </div>
        ) : null}
        <div className="grid gap-4 grid-cols-2">
          <Input label="Name" value={form.name || ""} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          {!hasParentCompanyContext ? (
            <Input label="Company ID" value={form.company_id?.toString() || ""} onChange={(e) => setForm((f) => ({ ...f, company_id: Number(e.target.value) }))} />
          ) : null}
          <Input label="Manager (Optional)" value={form.manager_name || ""} onChange={(e) => setForm((f) => ({ ...f, manager_name: e.target.value }))} />
          <Input label="Address (Optional)" value={form.address || ""} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} />
        </div>
        <div className="mt-6 flex justify-end">
          <Button onClick={() => void save()}>{editingId ? "Update Branch" : "Save Branch"}</Button>
        </div>
      </Modal>
      <Modal
        open={Boolean(deleteTarget)}
        title={deleteTarget ? `Remove ${deleteTarget.name}` : "Remove Branch"}
        onClose={() => {
          setDeleteTarget(null);
          setDeletePassword("");
          setDeleteError(null);
        }}
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-600">
            Type your password to remove{" "}
            <span className="font-semibold text-navy-900">{deleteTarget?.name || "this branch"}</span>.
          </p>
          <Input
            label="Mot de passe"
            type="password"
            error={deleteError}
            value={deletePassword}
            onChange={(event) => {
              setDeletePassword(event.target.value);
              if (deleteError) setDeleteError(null);
            }}
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void removeBranch()}>
              Remove Branch
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
