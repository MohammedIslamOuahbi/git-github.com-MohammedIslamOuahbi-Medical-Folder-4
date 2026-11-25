import { syncApi } from "@/api/syncApi";
import { useEffect } from "react";
import { syncService } from "@/services/syncService";
import { useSyncStore } from "@/store/syncStore";

let initialized = false;

export const useSync = () => {
  const queue = useSyncStore((state) => state.queue);
  const status = useSyncStore((state) => state.status);
  const conflicts = useSyncStore((state) => state.conflicts);
  const online = useSyncStore((state) => state.online);
  const syncing = useSyncStore((state) => state.syncing);
  const setOnline = useSyncStore((state) => state.setOnline);
  const setStatus = useSyncStore((state) => state.setStatus);

  useEffect(() => {
    const onOnline = () => {
      setOnline(true);
    };
    const onOffline = () => setOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, [setOnline]);

  useEffect(() => {
    if (initialized) return;
    initialized = true;
    void (async () => {
      try {
        const status = await syncApi.getStatus();
        setStatus(status);
      } catch {
        // Leave silent initial failure for offline-first behavior.
      }
    })();
  }, [setStatus]);

  return {
    queue,
    status,
    conflicts,
    online,
    syncing,
    syncNow: syncService.syncNow,
    resolveConflict: syncService.resolveConflict,
  };
};
