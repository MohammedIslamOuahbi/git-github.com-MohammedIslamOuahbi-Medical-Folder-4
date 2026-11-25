import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { branchesApi } from "@/api/branchesApi";
import { companiesApi } from "@/api/companiesApi";
import { drillingSitesApi } from "@/api/drillingSitesApi";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Input } from "@/components/common/Input";
import { Modal } from "@/components/common/Modal";
import { Pagination } from "@/components/common/Pagination";
import { SearchInput } from "@/components/common/SearchInput";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Select } from "@/components/common/Select";
import { DataTable } from "@/components/tables/DataTable";
import { usePaginatedResource } from "@/hooks/usePaginatedResource";
import type { Branch, Company, DrillingSite } from "@/types/entities";
import { mockSites } from "@/utils/mockData";

export const DrillingSitesPage = () => {
  const { items, total, page, pageSize, search, loading, error, setPage, setSearch, setItems } =
    usePaginatedResource<DrillingSite>(useCallback(drillingSitesApi.list, []), mockSites);
  const [open, setOpen] = useState(false);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [form, setForm] = useState<Partial<DrillingSite>>({
    status: "active",
  });

  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [companiesResponse, branchesResponse] = await Promise.all([
          companiesApi.list({ page_size: 500 }),
          branchesApi.list({ page_size: 1000 }),
        ]);
        setCompanies(companiesResponse.items);
        setBranches(branchesResponse.items);
      } catch {
        setCompanies([]);
        setBranches([]);
      }
    };

    void loadOptions();
  }, []);

  const columns = useMemo(
    () => [
      { key: "name", title: "Site", render: (row: DrillingSite) => row.name },
      { key: "branch", title: "Branch", render: (row: DrillingSite) => row.branch_name || row.branch_id },
      { key: "location", title: "Location", render: (row: DrillingSite) => row.location },
      { key: "status", title: "Status", render: (row: DrillingSite) => <Badge tone={row.status}>{row.status}</Badge> },
    ],
    [],
  );

  const companyOptions = useMemo(
    () => [
      { label: "Select company", value: "" },
      ...companies.map((company) => ({
        label: company.name,
        value: String(company.id),
      })),
    ],
    [companies],
  );

  const branchOptions = useMemo(() => {
    const filteredBranches = form.company_id
      ? branches.filter((branch) => branch.company_id === form.company_id)
      : [];

    return [
      { label: form.company_id ? "Select branch" : "Select company first", value: "" },
      ...filteredBranches.map((branch) => ({
        label: branch.name,
        value: String(branch.id),
      })),
    ];
  }, [branches, form.company_id]);

  const save = async () => {
    try {
      const created = await drillingSitesApi.create({
        ...form,
        company_id: Number(form.company_id),
        branch_id: Number(form.branch_id),
        name: form.name || "New Drilling Site",
        location: form.location || "",
        status: form.status || "active",
      });
      setItems((current) => [created, ...current]);
    } catch {
      const branch = branches.find((item) => item.id === form.branch_id);
      const company = companies.find((item) => item.id === form.company_id);
      const localRecord = {
        ...form,
        id: Date.now(),
        company_id: Number(form.company_id || 1),
        branch_id: Number(form.branch_id || 1),
        company_name: company?.name,
        branch_name: branch?.name,
        name: form.name || "Offline Drilling Site",
        location: form.location || "",
        status: form.status || "active",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      } as DrillingSite;
      setItems((current) => [localRecord, ...current]);
    } finally {
      setForm({ status: "active" });
      setOpen(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Field operations"
        title="Sites de forage"
        description={error || "Consultez les sites opérationnels actifs, leur état et leur rattachement aux filiales."}
        actionLabel="Créer un site de forage"
        actionIcon={Plus}
        onAction={() => {
          setForm({ status: "active" });
          setOpen(true);
        }}
      />
      <SearchInput value={search} onChange={setSearch} placeholder="Rechercher un site de forage..." />
      <DataTable columns={columns} data={items} loading={loading} uidScope="drilling-site" />
      <Pagination page={page} total={total} pageSize={pageSize} onPageChange={setPage} />
      <Modal open={open} title="Créer un site de forage" onClose={() => setOpen(false)}>
        <div className="grid gap-4 grid-cols-2">
          <Select
            label="Company"
            options={companyOptions}
            value={form.company_id?.toString() || ""}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                company_id: Number(event.target.value) || undefined,
                branch_id: undefined,
              }))
            }
          />
          <Select
            label="Branch"
            options={branchOptions}
            value={form.branch_id?.toString() || ""}
            disabled={!form.company_id}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                branch_id: Number(event.target.value) || undefined,
              }))
            }
          />
          <Input
            label="Nom du site"
            value={form.name || ""}
            onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
          />
          <Input
            label="Location"
            value={form.location || ""}
            onChange={(event) => setForm((current) => ({ ...current, location: event.target.value }))}
          />
          <Select
            label="Status"
            options={[
              { label: "Active", value: "active" },
              { label: "Inactive", value: "inactive" },
            ]}
            value={form.status || "active"}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                status: event.target.value as DrillingSite["status"],
              }))
            }
          />
        </div>
        <div className="mt-6 flex justify-end">
          <Button onClick={() => void save()}>Enregistrer le site de forage</Button>
        </div>
      </Modal>
    </div>
  );
};
