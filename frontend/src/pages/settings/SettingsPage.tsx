import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Clock3,
  Database,
  HardDriveDownload,
  Languages,
  RefreshCw,
  Save,
  ServerCog,
  Settings2,
  ShieldCheck,
  ShieldEllipsis,
  UserCog,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { SectionHeader } from "@/components/common/SectionHeader";
import { authApi } from "@/api/authApi";
import { useAuth } from "@/hooks/useAuth";
import { useSync } from "@/hooks/useSync";
import { hasPermission } from "@/utils/permissions";

const SETTINGS_STORAGE_KEY = "medical-folder:settings";

const defaultSystemForm = {
  app_name: "Medical Folder",
  clinic_identity: "Système médical Ibn Sina",
  environment_label: "Opérations de la clinique",
  default_language: "Français",
  timezone: "Africa/Algiers",
  dashboard_density: "Confortable",
  date_format: "DD/MM/YYYY",
  default_landing_page: "dashboard",
};

const defaultMedicalForm = {
  default_campaign_status: "draft",
  abnormal_review_flow: "doctor_review",
  result_visibility: "role_based",
  worker_uid_format: "10 caractères",
  report_default_scope: "campaign",
  default_result_status: "pending",
};

const defaultSyncForm = {
  auto_sync: "enabled",
  sync_interval: "15 minutes",
  conflict_resolution: "manual_review",
  offline_queue_alert: "enabled",
  sync_on_login: "enabled",
  background_retry: "enabled",
};

const defaultNotificationForm = {
  audit_alerts: "enabled",
  import_alerts: "enabled",
  abnormal_result_alerts: "enabled",
  daily_summary: "enabled",
  lock_status_alerts: "enabled",
  sync_failure_alerts: "enabled",
};

const defaultSecurityForm = {
  session_timeout: "60 minutes",
  device_access: "single_device",
  login_alerts: "enabled",
  audit_retention: "180 jours",
};

type SettingsPayload = {
  system: typeof defaultSystemForm;
  medical: typeof defaultMedicalForm;
  sync: typeof defaultSyncForm;
  notifications: typeof defaultNotificationForm;
  security: typeof defaultSecurityForm;
};

const settingSurface =
  "rounded-2xl border border-slate-200/80 bg-white/75 px-4 py-3 shadow-soft backdrop-blur-sm";

export const SettingsPage = () => {
  const { user, refreshProfile } = useAuth();
  const { status, online, syncing, syncNow, queue, conflicts } = useSync();
  const canManageSettings = hasPermission(user, "settings:manage");
  const isAdmin = canManageSettings;
  const [systemForm, setSystemForm] = useState(defaultSystemForm);
  const [medicalForm, setMedicalForm] = useState(defaultMedicalForm);
  const [syncForm, setSyncForm] = useState(defaultSyncForm);
  const [notificationForm, setNotificationForm] = useState(
    defaultNotificationForm,
  );
  const [securityForm, setSecurityForm] = useState(defaultSecurityForm);
  const [signaturePreview, setSignaturePreview] = useState("");
  const [signatureFile, setSignatureFile] = useState<File | null>(null);
  const [signatureSaving, setSignatureSaving] = useState(false);
  const [signatureNotice, setSignatureNotice] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saved">("idle");

  useEffect(() => {
    const stored = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!stored) return;

    try {
      const parsed = JSON.parse(stored) as Partial<SettingsPayload>;
      setSystemForm({ ...defaultSystemForm, ...(parsed.system || {}) });
      setMedicalForm({ ...defaultMedicalForm, ...(parsed.medical || {}) });
      setSyncForm({ ...defaultSyncForm, ...(parsed.sync || {}) });
      setNotificationForm({
        ...defaultNotificationForm,
        ...(parsed.notifications || {}),
      });
      setSecurityForm({ ...defaultSecurityForm, ...(parsed.security || {}) });
    } catch {
      localStorage.removeItem(SETTINGS_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (saveState !== "saved") return;
    const timeout = window.setTimeout(() => setSaveState("idle"), 2400);
    return () => window.clearTimeout(timeout);
  }, [saveState]);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    const currentUserSignatureUrl =
      user?.signatureUrl ??
      user?.signature_url ??
      user?.signatureImageUrl ??
      user?.signaturePngUrl ??
      user?.signature_png_url ??
      null;
    const currentUserHasSignature = Boolean(
      currentUserSignatureUrl || user?.hasSignature || user?.signature_png,
    );

    const loadSignaturePreview = async () => {
      if (!user || !canManageSettings) return;

      if (currentUserHasSignature && currentUserSignatureUrl) {
        try {
          const blob = await authApi.getMySignatureBlob();
          objectUrl = URL.createObjectURL(blob);
          if (active) {
            setSignaturePreview(objectUrl);
          }
          return;
        } catch {
          if (active) {
            setSignaturePreview("");
          }
          return;
        }
      }

      if (active) {
        setSignaturePreview(
          user.signature_png || currentUserSignatureUrl || "",
        );
      }
    };

    void loadSignaturePreview();

    return () => {
      active = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [
    canManageSettings,
    user?.hasSignature,
    user?.signature_png,
    user?.signatureImageUrl,
    user?.signatureUrl,
    user?.signature_url,
    user?.signaturePngUrl,
    user?.signature_png_url,
    user,
  ]);

  const fullName =
    user?.full_name ||
    `${user?.first_name || ""} ${user?.last_name || ""}`.trim() ||
    "Medical User";

  const accountSummary = useMemo(
    () => [
      { label: "Utilisateur", value: fullName },
      { label: "E-mail", value: user?.email || "Aucun e-mail" },
      { label: "Rôle", value: user?.role || "Inconnu" },
      {
        label: "Permissions",
        value: user?.permissions?.length
          ? `${user.permissions.length} assigned`
          : "Héritées du rôle",
      },
      { label: "Session", value: securityForm.session_timeout },
      { label: "Espace de travail", value: systemForm.environment_label },
    ],
    [
      fullName,
      securityForm.session_timeout,
      systemForm.environment_label,
      user,
    ],
  );

  const queueSummary = useMemo(
    () =>
      Object.entries(queue).reduce((sum, [, items]) => sum + items.length, 0),
    [queue],
  );

  const savePreferences = () => {
    if (!canManageSettings) return;
    const payload: SettingsPayload = {
      system: systemForm,
      medical: medicalForm,
      sync: syncForm,
      notifications: notificationForm,
      security: securityForm,
    };
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(payload));
    setSaveState("saved");
  };

  const resetPreferences = () => {
    if (!canManageSettings) return;
    localStorage.removeItem(SETTINGS_STORAGE_KEY);
    setSystemForm(defaultSystemForm);
    setMedicalForm(defaultMedicalForm);
    setSyncForm(defaultSyncForm);
    setNotificationForm(defaultNotificationForm);
    setSecurityForm(defaultSecurityForm);
    setSaveState("idle");
  };

  const handleSignatureUpload = (file?: File | null) => {
    if (!file) return;
    const hasPngExtension = file.name.toLowerCase().endsWith(".png");
    const hasPngMime =
      !file.type || file.type === "image/png" || file.type === "image/x-png";
    if (!hasPngExtension || !hasPngMime) {
      setSignatureNotice("Seuls les fichiers PNG sont autorises.");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setSignatureNotice("La signature doit faire 2 Mo maximum.");
      return;
    }
    setSignatureFile(file);
    setSignatureNotice(null);
    const reader = new FileReader();
    reader.onload = () => {
      setSignaturePreview(
        typeof reader.result === "string" ? reader.result : "",
      );
    };
    reader.readAsDataURL(file);
  };

  const handleSaveSignature = () => {
    const run = async () => {
      setSignatureSaving(true);
      setSignatureNotice(null);
      try {
        if (!signatureFile) {
          setSignatureNotice(
            "Choisissez un fichier PNG avant l'enregistrement.",
          );
          return;
        }
        await authApi.uploadMySignature(signatureFile);
        await refreshProfile();
        setSignatureFile(null);
        setSignatureNotice("Signature enregistrée dans votre profil.");
      } catch (error) {
        if (axios.isAxiosError(error)) {
          const detail = error.response?.data?.detail;
          const message =
            typeof detail === "string"
              ? detail
              : typeof detail?.message === "string"
                ? detail.message
                : "Impossible d'enregistrer la signature pour le moment.";
          setSignatureNotice(message);
          return;
        }
        setSignatureNotice(
          "Impossible d'enregistrer la signature pour le moment.",
        );
      } finally {
        setSignatureSaving(false);
      }
    };

    void run();
  };

  const handleRemoveSignature = () => {
    const run = async () => {
      setSignatureSaving(true);
      setSignatureNotice(null);
      try {
        await authApi.deleteMySignature();
        setSignatureFile(null);
        setSignaturePreview("");
        await refreshProfile();
        setSignatureNotice("Signature supprimée de votre profil.");
      } catch {
        setSignatureNotice(
          "Impossible de supprimer la signature pour le moment.",
        );
      } finally {
        setSignatureSaving(false);
      }
    };

    void run();
  };

  const syncConflictCount = conflicts.length || status?.conflict_count || 0;

  const restoreSignaturePreview = () => {
    setSignatureFile(null);
    setSignaturePreview(
      user?.signature_png ||
        user?.signatureUrl ||
        user?.signature_url ||
        user?.signatureImageUrl ||
        user?.signaturePngUrl ||
        user?.signature_png_url ||
        "",
    );
  };

  return (
    <div className="space-y-6 pb-8">
      <SectionHeader
        eyebrow="Administration système"
        title="Paramètres"
        description={
          canManageSettings
            ? "Centralisez les préférences de votre espace médical, la connectivité et votre signature professionnelle."
            : "Consultez les paramètres de la plateforme. Votre rôle dispose d’un accès en lecture seule."
        }
        actionLabel={
          canManageSettings
            ? saveState === "saved"
              ? "Préférences enregistrées"
              : "Enregistrer les préférences"
            : undefined
        }
        actionIcon={Save}
        onAction={canManageSettings ? savePreferences : undefined}
      />

      <section className="relative overflow-hidden rounded-[28px] border border-slate-200/80 bg-white shadow-sm">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-brand-500 via-cyan-500 to-emerald-500" />
        <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-brand-100/60 blur-3xl" />
        <div className="relative grid gap-6 p-5 sm:p-6 xl:grid-cols-[1.35fr_0.65fr] xl:p-8">
          <div className="flex min-w-0 flex-col justify-between gap-6">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1.5 text-xs font-bold text-brand-700">
                  <Settings2 className="h-3.5 w-3.5" />
                  Centre de configuration
                </span>
                <Badge tone={online ? "active" : "failed"}>
                  {online ? "Système en ligne" : "Mode hors ligne"}
                </Badge>
              </div>

              <h2 className="mt-5 max-w-3xl text-2xl font-black tracking-tight text-navy-950 sm:text-3xl">
                Gérez votre environnement médical depuis un espace unique.
              </h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-ink-500 sm:text-base">
                Identité du compte, synchronisation réseau, signature
                électronique et gouvernance des données.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-2">
              {[
               
                {
                  label: "File d’attente",
                  value: `${queueSummary} élément(s)`,
                  icon: RefreshCw,
                },
                {
                  label: "Conflits",
                  value: `${syncConflictCount} actif(s)`,
                  icon: ShieldEllipsis,
                },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.label}
                    className="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4 backdrop-blur"
                  >
                    <div className="flex items-center gap-2 text-slate-500">
                      <Icon className="h-4 w-4" />
                      <span className="text-[11px] font-black uppercase tracking-[0.12em]">
                        {item.label}
                      </span>
                    </div>
                    <p className="mt-2 truncate text-sm font-bold text-navy-950">
                      {item.value}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-950 p-5 text-white shadow-xl shadow-slate-950/10 sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
                  Synchronisation
                </p>
                <h3 className="mt-2 text-xl font-bold">
                  {syncing
                    ? "Synchronisation en cours"
                    : online
                      ? "Prêt à synchroniser"
                      : "Connexion indisponible"}
                </h3>
              </div>
              <div
                className={`rounded-2xl p-3 ${online ? "bg-emerald-400/15 text-emerald-300" : "bg-rose-400/15 text-rose-300"}`}
              >
                {online ? (
                  <Wifi className="h-5 w-5" />
                ) : (
                  <WifiOff className="h-5 w-5" />
                )}
              </div>
            </div>

            <div className="mt-6 space-y-3">
              <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-3">
                <span className="text-sm text-slate-400">
                  Dernière synchronisation
                </span>
                <span className="max-w-[55%] truncate text-right text-sm font-semibold text-white">
                  {status?.last_sync_at || "Aucune synchronisation"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-3">
                <span className="text-sm text-slate-400">
                  En attente d’envoi
                </span>
                <span className="text-sm font-bold text-white">
                  {status?.pending_push_count || 0}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-sm text-slate-400">
                  En attente de réception
                </span>
                <span className="text-sm font-bold text-white">
                  {status?.pending_pull_count || 0}
                </span>
              </div>
            </div>

            <Button
              className="mt-6 w-full justify-center"
              variant="secondary"
              icon={RefreshCw}
              loading={syncing}
              onClick={() => void syncNow().catch(() => undefined)}
            >
              Synchroniser maintenant
            </Button>
          </div>
        </div>
      </section>

      {!canManageSettings ? (
        <div className="flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-bold text-amber-950">Accès en lecture seule</p>
            <p className="mt-1 text-sm text-amber-800">
              Les modifications sont réservées aux utilisateurs autorisés à
              gérer les paramètres.
            </p>
          </div>
          <Badge tone="pending">Lecture seule</Badge>
        </div>
      ) : null}

      {canManageSettings ? (
        <Card className="border-slate-200/80 bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.14em] text-brand-600">
                Catalogue pharmaceutique
              </p>
              <h3 className="mt-1 text-xl font-bold text-navy-950">
                Importer la nomenclature officielle des médicaments
              </h3>
              <p className="mt-1 text-sm leading-6 text-ink-500">
                Analysez le fichier officiel, contrôlez le mapping des colonnes et importez le catalogue dans PostgreSQL.
              </p>
            </div>
            <Link
              to="/settings/medicines"
              className="inline-flex items-center justify-center rounded-xl bg-[#0085A3] px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-[#0085A3]/20 transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#00728c]"
            >
              Ouvrir le catalogue
            </Link>
          </div>
        </Card>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-1">
        
        {canManageSettings && user ? (
          <Card className="overflow-hidden border-slate-200/80 p-0">
            <div className="border-b border-slate-200 bg-gradient-to-r from-white to-brand-50/70 px-5 py-5 sm:px-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-brand-600">
                    Identité professionnelle
                  </p>
                  <h3 className="mt-1 text-xl font-bold text-navy-950">
                    Signature électronique PNG
                  </h3>
                  <p className="mt-1 max-w-2xl text-sm leading-6 text-ink-500">
                    Cette signature est utilisée sur les documents médicaux
                    validés par votre compte.
                  </p>
                </div>
                <Badge tone={user?.hasSignature ? "active" : "pending"}>
                  {user?.hasSignature ? "Signature active" : "Non configurée"}
                </Badge>
              </div>
            </div>

            <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[1fr_0.9fr]">
              <div className="space-y-4">
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 p-4">
                  <Input
                    type="file"
                    accept="image/png"
                    onChange={(event) =>
                      handleSignatureUpload(event.target.files?.[0] || null)
                    }
                  />
                  <p className="mt-3 text-xs leading-5 text-slate-500">
                    Format PNG uniquement. Fond transparent recommandé. Taille
                    maximale : 2 Mo.
                  </p>
                </div>

                <div className="flex flex-wrap gap-2.5">
                  <Button
                    onClick={handleSaveSignature}
                    loading={signatureSaving}
                    icon={Save}
                  >
                    {user?.hasSignature
                      ? "Remplacer la signature"
                      : "Enregistrer la signature"}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={handleRemoveSignature}
                    disabled={signatureSaving || !user?.hasSignature}
                  >
                    Supprimer
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={restoreSignaturePreview}
                    disabled={signatureSaving}
                  >
                    Restaurer l’aperçu
                  </Button>
                </div>

                {signatureNotice ? (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm font-semibold text-slate-700">
                    {signatureNotice}
                  </div>
                ) : null}
              </div>

              <div className="flex min-h-48 items-center justify-center rounded-2xl border border-slate-200 bg-[linear-gradient(45deg,#f8fafc_25%,transparent_25%),linear-gradient(-45deg,#f8fafc_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f8fafc_75%),linear-gradient(-45deg,transparent_75%,#f8fafc_75%)] bg-[length:20px_20px] bg-[position:0_0,0_10px,10px_-10px,-10px_0px] p-6">
                {signaturePreview ? (
                  <img
                    src={signaturePreview}
                    alt="Aperçu de la signature"
                    className="max-h-32 max-w-full object-contain"
                  />
                ) : (
                  <div className="text-center">
                    <ShieldCheck className="mx-auto h-8 w-8 text-slate-300" />
                    <p className="mt-3 text-sm font-semibold text-slate-500">
                      Aucune signature disponible
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      L’aperçu apparaîtra ici.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </Card>
        ) : (
          <Card className="flex items-center justify-center border-dashed border-slate-300 bg-slate-50/60">
            <div className="max-w-md py-8 text-center">
              <ShieldCheck className="mx-auto h-9 w-9 text-slate-300" />
              <h3 className="mt-4 text-lg font-bold text-navy-950">
                Signature protégée
              </h3>
              <p className="mt-2 text-sm leading-6 text-ink-500">
                La gestion de la signature est réservée aux comptes autorisés.
              </p>
            </div>
          </Card>
        )}
      </div>

      
    </div>
  );
};
