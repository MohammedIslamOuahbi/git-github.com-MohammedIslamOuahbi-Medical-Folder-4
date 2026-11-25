import { useEffect, useState } from "react";
import { Database, FileDown, Search, Upload } from "lucide-react";

import { medicinesApi } from "@/api/medicinesApi";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { SectionHeader } from "@/components/common/SectionHeader";
import { useAuth } from "@/hooks/useAuth";
import type { MedicineImportPreview, MedicineImportRecord, MedicineSearchItem } from "@/types/medicine";
import { hasPermission } from "@/utils/permissions";

export const MedicineCataloguePage = () => {
  const { user } = useAuth();
  const canManage = hasPermission(user, "settings:manage") || user?.role === "Admin" || user?.role === "Super Admin";
  const [file, setFile] = useState<File | null>(null);
  const [sourceName, setSourceName] = useState("Ministère de l’Industrie Pharmaceutique");
  const [sourceVersion, setSourceVersion] = useState("");
  const [publicationDate, setPublicationDate] = useState("");
  const [importMode, setImportMode] = useState("merge");
  const [notes, setNotes] = useState("");
  const [history, setHistory] = useState<MedicineImportRecord[]>([]);
  const [preview, setPreview] = useState<MedicineImportPreview | null>(null);
  const [currentImport, setCurrentImport] = useState<MedicineImportRecord | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<MedicineSearchItem[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadHistory = async () => {
    if (!canManage) return;
    try {
      setHistory(await medicinesApi.listImports());
    } catch {
      setNotice("Impossible de charger l’historique du catalogue.");
    }
  };

  useEffect(() => {
    void loadHistory();
  }, [canManage]);

  const handleAnalyze = async () => {
    if (!file) {
      setNotice("Sélectionnez d’abord le fichier officiel.");
      return;
    }
    setLoading(true);
    setNotice(null);
    try {
      const uploaded = await medicinesApi.uploadImport({
        file,
        source_name: sourceName,
        source_version: sourceVersion || undefined,
        import_mode: importMode,
        notes: notes || undefined,
      });
      setCurrentImport(uploaded);
      const nextPreview = await medicinesApi.previewImport(uploaded.id, uploaded.mapping_json || undefined);
      setPreview(nextPreview);
      await loadHistory();
    } catch {
      setNotice("Impossible d’analyser ce fichier de catalogue.");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!currentImport) return;
    setLoading(true);
    setNotice(null);
    try {
      const confirmed = await medicinesApi.confirmImport(currentImport.id, {
        source_name: sourceName,
        source_version: sourceVersion || undefined,
        publication_date: publicationDate || undefined,
        import_mode: importMode,
        notes: notes || undefined,
        mapping: preview?.selectedMapping,
      });
      setCurrentImport(confirmed);
      await loadHistory();
      setNotice("L’importation du catalogue a été lancée avec succès.");
    } catch {
      setNotice("Impossible de confirmer l’importation du catalogue.");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (value: string) => {
    setSearchTerm(value);
    if (!value.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      const result = await medicinesApi.search(value.trim(), 20);
      setSearchResults(result.items);
    } catch {
      setNotice("Impossible de rechercher les médicaments pour le moment.");
    }
  };

  if (!canManage) {
    return (
      <div className="space-y-6 pb-8">
        <SectionHeader
          eyebrow="Administration"
          title="Catalogue des médicaments"
          description="Cette section est réservée aux administrateurs autorisés."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-8">
      <SectionHeader
        eyebrow="Administration"
        title="Catalogue des médicaments"
        description="Importez et consultez la nomenclature officielle algérienne des produits pharmaceutiques."
      />

      {notice ? (
        <Card className="border-slate-200 bg-slate-50 p-4 text-sm font-semibold text-slate-700">
          {notice}
        </Card>
      ) : null}

      <Card className="space-y-4 border-slate-200 p-5">
        <div className="flex items-center gap-3">
          <Database className="h-5 w-5 text-cyan-700" />
          <h3 className="text-lg font-black text-slate-950">Importer le catalogue officiel</h3>
        </div>
        <Input type="file" accept=".xlsx,.csv,.json" onChange={(event) => setFile(event.target.files?.[0] || null)} />
        <div className="grid gap-4 md:grid-cols-2">
          <Input label="Source" value={sourceName} onChange={(event) => setSourceName(event.target.value)} />
          <Input label="Version" value={sourceVersion} onChange={(event) => setSourceVersion(event.target.value)} />
          <Input label="Date de publication" type="date" value={publicationDate} onChange={(event) => setPublicationDate(event.target.value)} />
          <Input label="Mode d'import" value={importMode} onChange={(event) => setImportMode(event.target.value)} />
        </div>
        <Input label="Notes" value={notes} onChange={(event) => setNotes(event.target.value)} />
        <div className="flex flex-wrap gap-3">
          <Button icon={Upload} onClick={handleAnalyze} loading={loading}>
            Analyser
          </Button>
          <Button variant="secondary" icon={FileDown} onClick={handleConfirm} disabled={!preview || loading}>
            Confirmer l'importation
          </Button>
        </div>
      </Card>

      {preview ? (
        <Card className="space-y-4 border-slate-200 p-5">
          <h3 className="text-lg font-black text-slate-950">Prévisualisation</h3>
          <div className="grid gap-3 md:grid-cols-3">
            <div>Total lignes: {preview.totalRows}</div>
            <div>Lignes valides: {preview.validRows}</div>
            <div>Lignes invalides: {preview.invalidRows}</div>
            <div>Inserts potentiels: {preview.potentialInserts}</div>
            <div>Mises à jour potentielles: {preview.potentialUpdates}</div>
            <div>Inchangés: {preview.unchangedRows}</div>
          </div>
          <div className="overflow-auto rounded-2xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left font-bold">Colonne source</th>
                  <th className="px-4 py-3 text-left font-bold">Champ cible</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {Object.entries(preview.selectedMapping).map(([source, target]) => (
                  <tr key={source}>
                    <td className="px-4 py-3">{source}</td>
                    <td className="px-4 py-3">{target}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      <Card className="space-y-4 border-slate-200 p-5">
        <div className="flex items-center gap-3">
          <Search className="h-5 w-5 text-cyan-700" />
          <h3 className="text-lg font-black text-slate-950">Recherche catalogue</h3>
        </div>
        <Input label="Recherche" value={searchTerm} onChange={(event) => void handleSearch(event.target.value)} />
        <div className="space-y-2">
          {searchResults.map((item) => (
            <div key={item.id} className="rounded-2xl border border-slate-200 px-4 py-3">
              <p className="font-bold text-slate-900">{item.brandName}</p>
              <p className="text-sm text-slate-600">
                {[item.genericName, item.strength, item.pharmaceuticalForm, item.laboratory].filter(Boolean).join(" • ")}
              </p>
            </div>
          ))}
          {!searchResults.length && searchTerm ? (
            <p className="text-sm text-slate-500">Aucun médicament trouvé.</p>
          ) : null}
        </div>
      </Card>

      <Card className="space-y-4 border-slate-200 p-5">
        <h3 className="text-lg font-black text-slate-950">Historique des imports</h3>
        <div className="space-y-2">
          {history.map((item) => (
            <div key={item.id} className="rounded-2xl border border-slate-200 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-bold text-slate-900">
                  {item.source_name} {item.source_version ? `• ${item.source_version}` : ""}
                </p>
                <span className="text-xs font-bold uppercase tracking-[0.08em] text-slate-500">{item.status}</span>
              </div>
              <p className="mt-1 text-sm text-slate-600">
                {item.original_file_name} • {item.inserted_rows} insérés • {item.updated_rows} mis à jour • {item.invalid_rows} invalides
              </p>
            </div>
          ))}
          {!history.length ? <p className="text-sm text-slate-500">Aucun import enregistré.</p> : null}
        </div>
      </Card>
    </div>
  );
};
