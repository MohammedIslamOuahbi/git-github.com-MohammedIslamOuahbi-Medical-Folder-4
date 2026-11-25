import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import { workspacesApi } from "@/api/workspacesApi";
import type { Workspace, WorkspaceCampaign, WorkspaceSession } from "@/types/workspace";
import { workspaceStorage } from "@/utils/storage";

interface CampaignWorkspaceContextValue {
  currentCampaign: WorkspaceCampaign | null;
  setCurrentCampaign: (campaign: WorkspaceCampaign | null) => void;
  currentWorkspace: Workspace | null;
  setCurrentWorkspace: (workspace: Workspace | null) => void;
  hasWorkspaceAccess: (campaignId: number | string) => boolean;
  unlockWorkspace: (campaignId: number | string, accessCode: string) => Promise<boolean>;
  exitWorkspace: (campaignId: number | string) => void;
  getWorkspaceSession: (campaignId: number | string) => WorkspaceSession | null;
}

const CampaignWorkspaceContext = createContext<CampaignWorkspaceContextValue | undefined>(
  undefined,
);

type WorkspaceSessionMap = Record<string, WorkspaceSession>;

export const CampaignWorkspaceProvider = ({
  children,
}: {
  children: ReactNode;
}) => {
  const [currentCampaign, setCurrentCampaign] = useState<WorkspaceCampaign | null>(null);
  const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(null);
  const [sessionMap, setSessionMap] = useState<WorkspaceSessionMap>(() => workspaceStorage.get<WorkspaceSessionMap>() || {});

  useEffect(() => {
    workspaceStorage.set(sessionMap);
  }, [sessionMap]);

  const hasWorkspaceAccess = useCallback(
    (campaignId: number | string) => Boolean(sessionMap[String(campaignId)]?.access_granted),
    [sessionMap],
  );

  const getWorkspaceSession = useCallback(
    (campaignId: number | string) => sessionMap[String(campaignId)] || null,
    [sessionMap],
  );

  const unlockWorkspace = useCallback(async (campaignId: number | string, accessCode: string) => {
    const session = await workspacesApi.accessByCampaign(campaignId, accessCode);
    setSessionMap((current) => ({
      ...current,
      [String(campaignId)]: session,
    }));
    return true;
  }, []);

  const exitWorkspace = useCallback((campaignId: number | string) => {
    const key = String(campaignId);
    setSessionMap((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setCurrentWorkspace((current) => (current && String(current.campaign_id) === key ? null : current));
  }, []);

  const value = useMemo<CampaignWorkspaceContextValue>(
    () => ({
      currentCampaign,
      setCurrentCampaign,
      currentWorkspace,
      setCurrentWorkspace,
      hasWorkspaceAccess,
      unlockWorkspace,
      exitWorkspace,
      getWorkspaceSession,
    }),
    [
      currentCampaign,
      currentWorkspace,
      exitWorkspace,
      getWorkspaceSession,
      hasWorkspaceAccess,
      unlockWorkspace,
    ],
  );

  return (
    <CampaignWorkspaceContext.Provider value={value}>
      {children}
    </CampaignWorkspaceContext.Provider>
  );
};

export const useCampaignWorkspace = () => {
  const context = useContext(CampaignWorkspaceContext);
  if (!context) {
    throw new Error(
      "useCampaignWorkspace must be used within CampaignWorkspaceProvider",
    );
  }
  return context;
};
