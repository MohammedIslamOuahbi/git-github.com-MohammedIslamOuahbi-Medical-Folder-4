import type { Role } from "@/types/common";

const ROLE_BADGE_CLASSNAMES: Record<Role, string> = {
  "Super Admin": "border-emerald-200 bg-emerald-50 text-emerald-700",
  Admin: "border-cyan-200 bg-cyan-50 text-cyan-700",
  Doctor: "border-violet-200 bg-violet-50 text-violet-700",
  Assistant: "border-amber-200 bg-amber-50 text-amber-700",
};

const ROLE_BADGE_TONES: Record<Role, string> = {
  "Super Admin": "super_admin",
  Admin: "admin",
  Doctor: "doctor",
  Assistant: "assistant",
};

export const getRoleBadgeClassName = (role: Role) => ROLE_BADGE_CLASSNAMES[role];
export const getRoleBadgeTone = (role: Role) => ROLE_BADGE_TONES[role];
