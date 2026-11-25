import {
  Activity,
  FileSpreadsheet,
  HardDriveDownload,
  Monitor,
  RefreshCcw,
  ShieldPlus,
  Users2,
} from "lucide-react";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";

const capabilities = [
  { icon: Users2, label: "Gestion des travailleurs" },
  { icon: ShieldPlus, label: "Dossiers medicaux complets" },
  { icon: Activity, label: "Campagnes medicales" },
  { icon: HardDriveDownload, label: "Synchronisation hors ligne" },
  { icon: FileSpreadsheet, label: "Rapports PDF et Excel" },
];

export const DesktopRequiredScreen = () => (
  <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[linear-gradient(145deg,#006e86_0%,#0085A3_45%,#11abc4_100%)] px-6 py-10 text-white">
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.22),transparent_22%),radial-gradient(circle_at_bottom_right,rgba(7,42,53,0.24),transparent_28%)]" />
    <div className="absolute left-[-8rem] top-[-10rem] h-72 w-72 rounded-full bg-white/10 blur-3xl" />
    <div className="absolute bottom-[-9rem] right-[-6rem] h-80 w-80 rounded-full bg-cyan-200/10 blur-3xl" />

    <Card className="relative z-10 w-full max-w-5xl overflow-hidden rounded-[2rem] border-white/55 bg-white/96 p-0 shadow-[0_40px_120px_-45px_rgba(6,38,48,0.55)] hover:translate-y-0 hover:shadow-[0_40px_120px_-45px_rgba(6,38,48,0.55)]">
      <div className="grid gap-0 grid-cols-[1.1fr_0.9fr]">
        <div className="relative overflow-hidden px-8 py-10 text-ink-900 px-10 py-12">
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#0085A3] via-cyan-400 to-[#006b84]" />

          <div className="mb-8 flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-brand-50 text-brand-700 shadow-soft">
              <Monitor className="h-7 w-7" />
            </div>

            <div className="flex items-center gap-3">
              <img
                src="/logo.png"
                alt="Medical Folder"
                className="h-12 w-12 rounded-2xl border border-slate-200/80 object-cover shadow-soft"
              />
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-brand-700">
                  Medical Folder
                </p>
                <p className="text-sm text-ink-500">Plateforme medicale professionnelle</p>
              </div>
            </div>
          </div>

          <div className="max-w-2xl space-y-4">
            <h1 className="font-display text-4xl leading-tight text-ink-900 text-[2.8rem]">
              Application disponible uniquement sur ordinateur
            </h1>
            <p className="max-w-xl text-base leading-7 text-ink-600">
              Medical Folder est concu pour les centres medicaux, les medecins et les
              assistants travaillant sur de grands ecrans afin de garantir une meilleure
              experience utilisateur.
            </p>
          </div>

          <div className="mt-8 grid gap-3 grid-cols-2">
            {capabilities.map(({ icon: Icon, label }) => (
              <div
                key={label}
                className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50/85 px-4 py-3 text-sm font-medium text-ink-700 shadow-sm"
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
                  <Icon className="h-4 w-4" />
                </div>
                <span>{label}</span>
              </div>
            ))}
          </div>

          <div className="mt-8 rounded-[1.75rem] border border-brand-100 bg-brand-50/65 px-5 py-4 text-sm leading-7 text-ink-700">
            Veuillez utiliser un ordinateur ou un ordinateur portable pour acceder a cette
            plateforme.
          </div>

          <div className="mt-8">
            <Button
              type="button"
              size="lg"
              icon={RefreshCcw}
              className="rounded-2xl px-6"
              onClick={() => window.location.reload()}
            >
              Actualiser
            </Button>
          </div>
        </div>

        <div className="relative hidden overflow-hidden bg-[linear-gradient(180deg,#f4fbfd_0%,#e4f5f9_100%)] p-8 block">
          <div className="absolute right-8 top-8 h-28 w-28 rounded-full bg-brand-100/60 blur-2xl" />
          <div className="absolute bottom-10 left-8 h-32 w-32 rounded-full bg-cyan-100 blur-3xl" />

          <div className="relative flex h-full min-h-[34rem] items-center justify-center">
            <div className="absolute inset-x-8 top-10 h-12 rounded-full bg-white/65 blur-2xl" />

            <div className="relative w-full max-w-md">
              <div className="absolute -left-6 top-8 flex h-20 w-20 items-center justify-center rounded-[1.75rem] border border-white/80 bg-white/90 text-brand-700 shadow-soft">
                <ShieldPlus className="h-10 w-10" />
              </div>

              <div className="absolute -right-3 top-24 flex h-16 w-16 items-center justify-center rounded-[1.5rem] border border-white/80 bg-white/90 text-emerald-600 shadow-soft">
                <Activity className="h-8 w-8" />
              </div>

              <div className="absolute -right-4 bottom-14 flex h-16 w-16 items-center justify-center rounded-[1.5rem] border border-white/80 bg-white/90 text-sky-600 shadow-soft">
                <FileSpreadsheet className="h-8 w-8" />
              </div>

              <div className="rounded-[2rem] border border-slate-200/80 bg-white p-5 shadow-[0_30px_70px_-34px_rgba(15,23,42,0.35)]">
                <div className="rounded-[1.75rem] bg-[linear-gradient(180deg,#0b748c_0%,#0e90ac_100%)] p-5">
                  <div className="rounded-[1.5rem] border border-white/15 bg-slate-950/10 p-4">
                    <div className="mb-4 flex items-center justify-between">
                      <div>
                        <p className="text-xs uppercase tracking-[0.24em] text-cyan-100/90">
                          Secure Workspace
                        </p>
                        <p className="mt-1 text-lg font-semibold text-white">
                          Medical Folder
                        </p>
                      </div>
                      <div className="rounded-2xl bg-white/12 p-3 text-white">
                        <Monitor className="h-6 w-6" />
                      </div>
                    </div>

                    <div className="grid gap-3">
                      <div className="rounded-2xl bg-white/14 p-3">
                        <div className="mb-2 h-2.5 w-24 rounded-full bg-white/80" />
                        <div className="h-2 w-full rounded-full bg-white/30" />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-2xl bg-white/14 p-3">
                          <div className="mb-6 h-16 rounded-xl bg-white/20" />
                          <div className="h-2 w-3/4 rounded-full bg-white/35" />
                        </div>
                        <div className="rounded-2xl bg-white/14 p-3">
                          <div className="mb-6 h-16 rounded-xl bg-white/20" />
                          <div className="h-2 w-2/3 rounded-full bg-white/35" />
                        </div>
                      </div>
                      <div className="rounded-2xl bg-white/14 p-3">
                        <div className="mb-2 flex items-center gap-2">
                          <div className="h-8 w-8 rounded-xl bg-white/25" />
                          <div className="h-2 w-28 rounded-full bg-white/45" />
                        </div>
                        <div className="h-2 w-full rounded-full bg-white/25" />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-3 gap-3">
                  {["Grand ecran", "Flux securise", "Usage clinique"].map((item) => (
                    <div
                      key={item}
                      className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-4 text-center text-xs font-semibold uppercase tracking-[0.14em] text-ink-500"
                    >
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>
  </div>
);

