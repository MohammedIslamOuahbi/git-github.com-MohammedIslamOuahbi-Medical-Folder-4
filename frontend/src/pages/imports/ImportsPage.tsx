import { useState } from "react";
import { Upload } from "lucide-react";
import { importsApi } from "@/api/importsApi";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { SectionHeader } from "@/components/common/SectionHeader";
import type { ImportJob } from "@/types/entities";

export const ImportsPage = () => {
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onUpload = async () => {
    if (!file) return;
    setLoading(true);
    setMessage(null);
    try {
      const created = await importsApi.upload(file);
      setJob(created);
      setMessage("File uploaded successfully. Continue with preview, validation, and confirmation.");
    } catch {
      setJob({
        id: Date.now(),
        filename: file.name,
        status: "pending",
        imported_rows: 0,
        validation_errors: 0,
        duplicate_rows: 0,
        uploaded_by: "Offline User",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      setMessage("Upload API unavailable. Draft import job created locally.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Bulk intake"
        title="Importer les travailleurs"
        description="Téléversez des fichiers Excel ou CSV pour l'intégration des travailleurs, prévisualisez les correspondances, validez les lignes et confirmez les importations."
      />
      <Card className="space-y-4">
        <div className="rounded-[24px] border border-dashed border-brand-200 bg-brand-50/60 p-8 text-center">
          <Upload className="mx-auto h-10 w-10 text-brand-700" />
          <p className="mt-4 text-lg font-medium text-ink-900">Déposez un fichier Excel ou CSV ici</p>
          <p className="mt-2 text-sm text-ink-500">
            Prend en charge les formats `.xlsx`, `.xls`, `.csv` avec les données des travailleurs et de préparation de campagne.
          </p>
          <input
            type="file"
            accept=".xlsx,.xls,.csv"
            className="mx-auto mt-6 block text-sm"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          <div className="mt-6">
            <Button onClick={() => void onUpload()} loading={loading}>
              Téléverser le fichier
            </Button>
          </div>
        </div>
        {message && <p className="text-sm text-ink-600">{message}</p>}
        {job && (
          <div className="grid gap-4 rounded-3xl bg-ink-50 p-5 grid-cols-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink-500">Fichier</p>
              <p className="mt-2 font-medium text-ink-900">{job.filename}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink-500">Status</p>
              <div className="mt-2">
                <Badge tone={job.status}>{job.status}</Badge>
              </div>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink-500">Lignes</p>
              <p className="mt-2 font-medium text-ink-900">{job.imported_rows}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink-500">Erreurs de validation</p>
              <p className="mt-2 font-medium text-ink-900">{job.validation_errors}</p>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
