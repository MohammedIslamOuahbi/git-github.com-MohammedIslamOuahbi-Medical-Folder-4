import type { AuthUser } from "@/types/auth";

const toSeed = (scope: string) =>
  scope
    .toUpperCase()
    .split("")
    .reduce((total, char, index) => total + char.charCodeAt(0) * (index + 17), 0);

const toBase36 = (value: bigint) => value.toString(36).toUpperCase();

const normalizePrefix = (scope: string) =>
  scope
    .replace(/[^A-Za-z0-9]/g, "")
    .toUpperCase()
    .padEnd(2, "X")
    .slice(0, 2);

export const buildEntityUid = (scope: string, id: number | string) => {
  const numericId = BigInt(typeof id === "number" ? id : Number.parseInt(String(id), 10) || 0);
  const seed = BigInt(toSeed(scope));
  const encoded = toBase36(seed * 1000003n + numericId * 97n).padStart(8, "0").slice(-8);
  return `${normalizePrefix(scope)}${encoded}`;
};

export const buildUserDashboardUid = (user: Pick<AuthUser, "id" | "role">) =>
  buildEntityUid(`dashboard-${user.role}`, user.id);

export const isMatchingDashboardUid = (
  dashboardUid: string | undefined,
  user: Pick<AuthUser, "id" | "role"> | null,
) => {
  if (!dashboardUid || !user) return false;
  return dashboardUid.toUpperCase() === buildUserDashboardUid(user).toUpperCase();
};
