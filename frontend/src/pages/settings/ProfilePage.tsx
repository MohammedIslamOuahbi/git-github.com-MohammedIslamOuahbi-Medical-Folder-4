import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  CheckCircle2,
  Mail,
  Save,
  ShieldCheck,
  UserRound,
  UserRoundCog,
} from "lucide-react";

import { authApi } from "@/api/authApi";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Input } from "@/components/common/Input";
import { SectionHeader } from "@/components/common/SectionHeader";
import { useAuth } from "@/hooks/useAuth";

export const ProfilePage = () => {
  const { user, refreshProfile } = useAuth();

  const [signaturePreview, setSignaturePreview] = useState("");
  const [signatureFile, setSignatureFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const canManageSignature =
    user?.role === "Doctor" ||
    user?.role === "Admin" ||
    user?.role === "Super Admin";

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

    const loadPreview = async () => {
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
        setSignaturePreview(user?.signature_png || currentUserSignatureUrl || "");
      }
    };

    void loadPreview();

    return () => {
      active = false;

      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [
    user?.hasSignature,
    user?.signature_png,
    user?.signatureImageUrl,
    user?.signatureUrl,
    user?.signature_url,
    user?.signaturePngUrl,
    user?.signature_png_url,
  ]);

  const fullName = useMemo(
    () =>
      user?.full_name ||
      `${user?.first_name || ""} ${user?.last_name || ""}`.trim() ||
      "Utilisateur médical",
    [user?.first_name, user?.full_name, user?.last_name],
  );

  const initials = useMemo(
    () =>
      fullName
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part.charAt(0).toUpperCase())
        .join("") || "U",
    [fullName],
  );

  const permissions = user?.permissions || [];

  const handleSignatureUpload = (file?: File | null) => {
    if (!file) return;

    const hasPngExtension = file.name.toLowerCase().endsWith(".png");
    const hasPngMime =
      !file.type || file.type === "image/png" || file.type === "image/x-png";

    if (!hasPngExtension || !hasPngMime) {
      setNotice("Seuls les fichiers PNG sont autorisés.");
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      setNotice("La signature doit faire 2 Mo maximum.");
      return;
    }

    setSignatureFile(file);
    setNotice(null);

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
      setSaving(true);
      setNotice(null);

      try {
        if (!signatureFile) {
          setNotice("Choisissez un fichier PNG avant l’enregistrement.");
          return;
        }

        await authApi.uploadMySignature(signatureFile);
        await refreshProfile();

        setSignatureFile(null);
        setNotice("Signature enregistrée dans votre profil.");
      } catch (error) {
        if (axios.isAxiosError(error)) {
          const detail = error.response?.data?.detail;

          const message =
            typeof detail === "string"
              ? detail
              : typeof detail?.message === "string"
                ? detail.message
                : "Impossible d’enregistrer la signature pour le moment.";

          setNotice(message);
          return;
        }

        setNotice("Impossible d’enregistrer la signature pour le moment.");
      } finally {
        setSaving(false);
      }
    };

    void run();
  };

  const handleRemoveSignature = () => {
    const run = async () => {
      setSaving(true);
      setNotice(null);

      try {
        await authApi.deleteMySignature();

        setSignatureFile(null);
        setSignaturePreview("");

        await refreshProfile();

        setNotice("Signature supprimée de votre profil.");
      } catch {
        setNotice("Impossible de supprimer la signature pour le moment.");
      } finally {
        setSaving(false);
      }
    };

    void run();
  };

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
        eyebrow="Compte utilisateur"
        title="Profil"
        description="Consultez votre identité, votre rôle, vos autorisations et votre signature professionnelle."
      />

      <section className="relative overflow-hidden rounded-[28px] border border-slate-200/80 bg-white shadow-sm">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-brand-500 via-cyan-500 to-emerald-500" />
        <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-brand-100/60 blur-3xl" />

        <div className="relative grid gap-6 p-5 sm:p-6 xl:grid-cols-[1.25fr_0.75fr] xl:p-8">
          <div className="flex min-w-0 flex-col justify-between gap-6">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
              <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-3xl bg-slate-950 text-2xl font-black text-white shadow-lg shadow-slate-950/10">
                {initials}
              </div>

              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="active">Compte actif</Badge>
                  <Badge tone="reviewed">{user?.role || "Utilisateur"}</Badge>
                </div>

                <h2 className="mt-3 truncate text-2xl font-black tracking-tight text-navy-950 sm:text-3xl">
                  {fullName}
                </h2>

                <p className="mt-2 flex items-center gap-2 text-sm text-ink-500">
                  <Mail className="h-4 w-4 shrink-0" />
                  <span className="truncate">{user?.email || "Aucun e-mail"}</span>
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[
                {
                  label: "Rôle",
                  value: user?.role || "Inconnu",
                  icon: UserRoundCog,
                },
                {
                  label: "Permissions",
                  value: permissions.length
                    ? `${permissions.length} attribuée(s)`
                    : "Héritées du rôle",
                  icon: ShieldCheck,
                },
                {
                  label: "Signature",
                  value: user?.hasSignature ? "Configurée" : "Non configurée",
                  icon: CheckCircle2,
                },
              ].map((item) => {
                const Icon = item.icon;

                return (
                  <div
                    key={item.label}
                    className="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4"
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
                  Informations du compte
                </p>
                <h3 className="mt-2 text-xl font-bold">Résumé utilisateur</h3>
              </div>

              <div className="rounded-2xl bg-white/10 p-3 text-sky-300">
                <UserRound className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-6 space-y-3">
              {[
                { label: "Nom complet", value: fullName },
                { label: "Adresse e-mail", value: user?.email || "Non renseignée" },
                { label: "Rôle attribué", value: user?.role || "Inconnu" },
                {
                  label: "Gestion de signature",
                  value: canManageSignature ? "Autorisée" : "Non autorisée",
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="flex items-center justify-between gap-4 border-b border-white/10 pb-3 last:border-b-0 last:pb-0"
                >
                  <span className="text-sm text-slate-400">{item.label}</span>
                  <span className="max-w-[58%] truncate text-right text-sm font-semibold text-white">
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {canManageSignature ? (
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
                  Cette signature sera utilisée uniquement sur les documents médicaux
                  validés ou signés avec votre compte.
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
                  Format PNG uniquement. Fond transparent recommandé. Taille maximale :
                  2 Mo.
                </p>
              </div>

              <div className="flex flex-wrap gap-2.5">
                <Button
                  onClick={handleSaveSignature}
                  loading={saving}
                  icon={Save}
                >
                  {user?.hasSignature
                    ? "Remplacer la signature"
                    : "Enregistrer la signature"}
                </Button>

                <Button
                  variant="secondary"
                  onClick={handleRemoveSignature}
                  disabled={saving || !user?.hasSignature}
                >
                  Supprimer
                </Button>

                <Button
                  variant="ghost"
                  onClick={restoreSignaturePreview}
                  disabled={saving}
                >
                  Restaurer l’aperçu
                </Button>
              </div>

              {notice ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm font-semibold text-slate-700">
                  {notice}
                </div>
              ) : null}
            </div>

            <div className="flex min-h-52 items-center justify-center rounded-2xl border border-slate-200 bg-[linear-gradient(45deg,#f8fafc_25%,transparent_25%),linear-gradient(-45deg,#f8fafc_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f8fafc_75%),linear-gradient(-45deg,transparent_75%,#f8fafc_75%)] bg-[length:20px_20px] bg-[position:0_0,0_10px,10px_-10px,-10px_0px] p-6">
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
              La gestion de la signature est réservée aux médecins, administrateurs
              et super administrateurs.
            </p>
          </div>
        </Card>
      )}

      <Card className="border-slate-200/80">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">
            Autorisations
          </p>

          <h3 className="mt-2 text-xl font-bold text-navy-950">
            Périmètre du compte
          </h3>

          <p className="mt-1 text-sm leading-6 text-ink-500">
            Autorisations directement attribuées ou héritées du rôle utilisateur.
          </p>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {permissions.length ? (
            permissions.map((permission) => (
              <span
                key={permission}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700"
              >
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                {permission}
              </span>
            ))
          ) : (
            <Badge tone="reviewed">Autorisations héritées du rôle</Badge>
          )}
        </div>
      </Card>
    </div>
  );
};