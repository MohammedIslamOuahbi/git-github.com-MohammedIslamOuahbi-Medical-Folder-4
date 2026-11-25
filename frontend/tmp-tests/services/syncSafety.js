export const SYNC_SAFETY_CODE = "OPERATION_SUSPENDED_FOR_DATA_SAFETY";
export const SYNC_SAFETY_MESSAGE = "Synchronisation suspendue pour proteger les donnees. Les elements presents dans le stockage actuel ne sont pas supprimes par cette operation. Leur conservation depend de ce stockage jusqu'a la reprise durable. Aucun element deja efface n'est restaure.";
export const suspendedSyncError = () => Object.assign(new Error(`${SYNC_SAFETY_CODE}: ${SYNC_SAFETY_MESSAGE}`), { code: SYNC_SAFETY_CODE, retryable: false });
export const isSafetySuspension = (error) => {
    const candidate = error;
    return candidate?.code === SYNC_SAFETY_CODE ||
        candidate?.response?.data?.details?.code === SYNC_SAFETY_CODE ||
        Boolean(candidate?.message?.includes(SYNC_SAFETY_CODE)) ||
        Boolean(candidate?.response?.data?.message?.includes(SYNC_SAFETY_CODE));
};
export const requireSuccessfulDesktopOperation = (result) => {
    if (!result || !result.success) {
        if (result?.operationState === SYNC_SAFETY_CODE)
            throw suspendedSyncError();
        throw new Error(result?.message || "Operation desktop indisponible.");
    }
    return result;
};
