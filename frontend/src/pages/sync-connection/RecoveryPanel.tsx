import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { useAuth } from "@/hooks/useAuth";
import { legacyRecovery, type RecoverySourceSummary } from "@/services/legacyRecovery";

const JOURNALS = ["sync_changes", "client_sync_changes", "client_local_sync_runs", "client_local_sync_state", "device_sync_states", "sync_conflicts"];

const statusLabel: Record<RecoverySourceSummary["state"], string> = {
  captured: "Source capturée; inscription des éléments à poursuivre",
  recorded: "Éléments inscrits au registre; en attente du moteur unifié",
  needs_review: "Vérification humaine nécessaire",
};

export const RecoveryPanel = () => {
  const { user } = useAuth();
  const isAdmin = ["admin", "super_admin"].includes((user?.role || "").toLowerCase());
  const [sources, setSources] = useState<RecoverySourceSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<Array<{ ordinal: number; state: string; reason_code: string | null }>>([]);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [moreItems, setMoreItems] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const refresh = async () => {
    const result = await legacyRecovery.listSources();
    setSources(result.sources);
  };
  useEffect(() => { void refresh().catch(() => setError("Registre indisponible sur l'API connectée; la migration PostgreSQL peut être encore absente.")); }, []);
  const act = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try { await action(); await refresh(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Capture indisponible."); }
    finally { setBusy(false); }
  };
  return (
    <Card className="space-y-4 p-5">
      <h3 className="text-lg font-bold">Registre de récupération</h3>
      <p className="text-sm text-slate-600">Capture dans PostgreSQL du serveur API actuellement connecté. Les sources d'origine ne sont pas supprimées. Aucun élément n'est appliqué au dossier médical.</p>
      <div className="flex flex-wrap gap-2">
        <Button disabled={busy} onClick={() => void act(() => legacyRecovery.captureBrowser())}>Capturer la file et les brouillons de ce navigateur</Button>
        {isAdmin ? <Button disabled={busy} variant="secondary" onClick={() => fileInput.current?.click()}>Sélectionner un ancien paquet</Button> : null}
        <input ref={fileInput} type="file" accept=".sync,.json" className="hidden" onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void act(() => legacyRecovery.capturePackage(file));
          event.target.value = "";
        }} />
        <Button disabled={busy} variant="secondary" onClick={() => void act(refresh)}>Actualiser</Button>
        {isAdmin ? <Button disabled={busy} variant="secondary" onClick={() => void act(async () => {
          for (const table of JOURNALS) {
            setProgress(`Lecture du journal ${table}`);
            let after = 0;
            while (true) {
              const page = await legacyRecovery.captureJournalPage(table, after);
              if (!page.has_more) break;
              if (page.next_after_id <= after) throw new Error("RECOVERY_JOURNAL_CURSOR_INVALID");
              after = page.next_after_id;
            }
          }
          setProgress("Lecture des journaux terminée. Les éléments restent au registre.");
        })}>Capturer les journaux PostgreSQL</Button> : null}
      </div>
      {progress ? <p role="status" className="text-sm text-slate-600">{progress}</p> : null}
      {error ? <p role="alert" className="text-sm text-rose-700">{error}</p> : null}
      <p className="text-sm">{sources.length} source(s) visibles; {sources.reduce((sum, source) => sum + source.materialized_count, 0)} élément(s) inscrits. Affichage limité aux 200 dernières sources.</p>
      <div className="max-h-72 space-y-2 overflow-auto">
        {sources.map((source) => <div key={source.uuid} className="rounded border p-3 text-sm">
          <p>{source.source_kind} — {statusLabel[source.state]}</p>
          <p>{source.materialized_count}/{source.item_count} éléments • {source.reason_code || "Aucune raison de blocage"}</p>
          {!source.source_identity_present ? <p>Identité de l'appareil à vérifier.</p> : null}
          {source.materialized_count < source.item_count ? <Button disabled={busy} variant="secondary" onClick={() => void act(() => legacyRecovery.resume(source.uuid))}>Poursuivre l'inscription</Button> : null}
          <Button disabled={busy} variant="secondary" onClick={() => void act(async () => {
            const result = await legacyRecovery.listItemStatuses(source.uuid);
            setSelectedSource(source.uuid);
            setItems(result.items);
            setMoreItems(result.has_more);
          })}>Voir les états des éléments</Button>
        </div>)}
      </div>
      {items.length ? <div className="max-h-36 overflow-auto text-xs">{items.map((item) => <p key={item.ordinal}>Élément {item.ordinal + 1}: {item.state} {item.reason_code || ""}</p>)}</div> : null}
      {selectedSource && moreItems ? <Button disabled={busy} variant="secondary" onClick={() => void act(async () => {
        const result = await legacyRecovery.listItemStatuses(selectedSource, items[items.length - 1]?.ordinal ?? -1);
        setItems((current) => [...current, ...result.items]);
        setMoreItems(result.has_more);
      })}>Voir la page suivante des états</Button> : null}
    </Card>
  );
};
