/** Persist only retry identity and payload hash, never medical request content. */
export const mutationHeaders = async (entityId: number | string, action: string, version: number | undefined, payload: unknown) => {
  if (action !== "create" && !action.startsWith("duplicate:") && (!Number.isInteger(version) || !version || version < 1)) {
    throw new Error("EXPECTED_VERSION_REQUIRED");
  }
  const key = `medical_visit_pending_operation:${entityId}:${action}`;
  const bytes = new TextEncoder().encode(JSON.stringify({ version, payload }));
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), (byte) => byte.toString(16).padStart(2, "0")).join("");
  let saved: { hash: string; operation_uuid: string } | null = null;
  try { saved = JSON.parse(window.localStorage.getItem(key) || "null"); } catch { /* ignore malformed metadata */ }
  if (!saved || saved.hash !== hash) {
    saved = { hash, operation_uuid: crypto.randomUUID() };
    window.localStorage.setItem(key, JSON.stringify(saved));
  }
  return { key, headers: { "X-Expected-Version": String(version), "X-Operation-UUID": saved.operation_uuid } };
};

export const savedConflictMessage = (error: unknown): string | null => {
  const response = (error as { response?: { status?: number; data?: { message?: string; details?: { attempt_saved?: boolean } } } })?.response;
  if (response?.status !== 409 || response.data?.message !== "EXPECTED_VERSION_CONFLICT") return null;
  return response.data.details?.attempt_saved
    ? "Une autre modification a ete enregistree. Votre tentative reste disponible pour examen; gardez le formulaire ouvert."
    : "Une autre modification a ete enregistree. Gardez le formulaire ouvert et verifiez votre saisie.";
};
