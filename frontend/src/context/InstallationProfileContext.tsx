import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { installationApi } from "@/api/installationApi";
import { detectProfileMismatch, isCentralProfile } from "@/features/central/centralServerFlow";
import {
  createBackendUnavailableWarning,
  deriveInstallationCapabilities,
  deriveDeviceIdentity,
  resolveEffectiveProfile,
  type InstallationProfile,
} from "@/features/installation/profileInfrastructure";
import type {
  InstallationErrorCode,
  InstallationProfileCapabilities,
  InstallationProfileLoadState,
  InstallationProfilePayload,
  InstallationProfileSource,
  InstallationStatusPayload,
  InstallationWarning,
} from "@/types/installation";

type InstallationProfileContextValue = {
  loading: boolean;
  error: string | null;
  status: InstallationProfileLoadState;
  profile: InstallationProfile | null;
  backendProfile: InstallationProfile | null;
  packagedProfile: InstallationProfile | null;
  source: InstallationProfileSource;
  warning: InstallationWarning | null;
  profilePayload: InstallationProfilePayload | null;
  capabilities: InstallationProfileCapabilities | null;
  capabilitiesLoaded: boolean;
  provisioningStatus: string;
  deviceIdentity: {
    uuid: string | null;
    code: string | null;
    name: string | null;
    centralUuid: string | null;
  };
  installationStatus: InstallationStatusPayload | null;
  mismatchError: InstallationErrorCode | null;
  refresh: () => Promise<void>;
  refreshProfile: () => Promise<InstallationProfilePayload | null>;
  refreshStatus: () => Promise<InstallationStatusPayload | null>;
  isCentralServer: boolean;
};

const InstallationProfileContext = createContext<InstallationProfileContextValue | undefined>(undefined);
let sharedProfileRequest: Promise<InstallationProfilePayload> | null = null;
let sharedStatusRequest: Promise<InstallationStatusPayload> | null = null;

const readPackagedProfile = () => {
  const value = import.meta.env.VITE_INSTALLATION_PROFILE;
  if (value === "central_server" || value === "mobile_device") {
    return value;
  }
  return null;
};

type InstallationProfileState = {
  effectiveProfile: InstallationProfile | null;
  backendProfile: InstallationProfile | null;
  packagedProfile: InstallationProfile | null;
  lastKnownGoodProfile: InstallationProfile | null;
  source: InstallationProfileSource;
  status: InstallationProfileLoadState;
  warning: InstallationWarning | null;
  error: string | null;
  profilePayload: InstallationProfilePayload | null;
  installationStatus: InstallationStatusPayload | null;
};

const getProfileError = (error: unknown) =>
  error instanceof Error ? error.message : "Impossible de charger le profil.";

const createInitialState = (packagedProfile: InstallationProfile | null): InstallationProfileState => {
  const resolved = resolveEffectiveProfile({
    backendProfile: null,
    lastKnownGoodProfile: null,
    packagedProfile,
  });

  return {
    effectiveProfile: resolved.profile,
    backendProfile: null,
    packagedProfile,
    lastKnownGoodProfile: null,
    source: resolved.source,
    status: packagedProfile ? "fallback" : "idle",
    warning: null,
    error: null,
    profilePayload: null,
    installationStatus: null,
  };
};

export const InstallationProfileProvider = ({ children }: { children: ReactNode }) => {
  const packagedProfile = readPackagedProfile();
  const [state, setState] = useState<InstallationProfileState>(() => createInitialState(packagedProfile));
  const requestSequenceRef = useRef(0);

  useEffect(() => {
    setState((current) => {
      const resolved = resolveEffectiveProfile({
        backendProfile: current.backendProfile,
        lastKnownGoodProfile: current.lastKnownGoodProfile,
        packagedProfile,
      });

      return {
        ...current,
        packagedProfile,
        effectiveProfile: resolved.profile,
        source: resolved.source,
        status:
          current.status === "idle" && packagedProfile
            ? "fallback"
            : current.status,
      };
    });
  }, [packagedProfile]);

  const refreshProfile = useCallback(async () => {
    if (!sharedProfileRequest) {
      sharedProfileRequest = installationApi.getProfile().finally(() => {
        sharedProfileRequest = null;
      });
    }
    const nextProfile = await sharedProfileRequest;
    return {
      ...nextProfile,
      packaged_profile: packagedProfile,
    };
  }, [packagedProfile]);

  const refreshStatus = useCallback(async () => {
    if (!sharedStatusRequest) {
      sharedStatusRequest = installationApi.getStatus().finally(() => {
        sharedStatusRequest = null;
      });
    }
    return sharedStatusRequest;
  }, []);

  const refresh = useCallback(async (includeStatus = true) => {
    const requestId = ++requestSequenceRef.current;
    setState((current) => ({
      ...current,
      status: current.effectiveProfile ? current.status : "loading",
      warning: null,
      error: null,
    }));

    const [profileResult, statusResult] = await Promise.allSettled([
      refreshProfile(),
      includeStatus ? refreshStatus() : Promise.resolve(null),
    ]);

    if (requestId !== requestSequenceRef.current) {
      return;
    }

    if (profileResult.status === "rejected") {
      setState((current) => {
        const resolved = resolveEffectiveProfile({
          backendProfile: null,
          lastKnownGoodProfile: current.lastKnownGoodProfile,
          packagedProfile: current.packagedProfile,
        });

        return {
          ...current,
          backendProfile: null,
          effectiveProfile: resolved.profile,
          source: resolved.source,
          status: resolved.profile ? "degraded" : "error",
          warning: resolved.profile ? createBackendUnavailableWarning() : null,
          error: resolved.profile ? null : getProfileError(profileResult.reason),
        };
      });
      return;
    }

    const nextProfile = profileResult.value;
    const nextStatus = includeStatus && statusResult.status === "fulfilled" ? statusResult.value : null;

    setState((current) => {
      const backendProfile = nextProfile.profile;
      const lastKnownGoodProfile = backendProfile ?? current.lastKnownGoodProfile;
      const resolved = resolveEffectiveProfile({
        backendProfile,
        lastKnownGoodProfile,
        packagedProfile: current.packagedProfile,
      });
      const degradedWarning =
        includeStatus && statusResult.status === "rejected" && resolved.profile ? createBackendUnavailableWarning() : null;
      const nextStatusValue: InstallationProfileLoadState = backendProfile
        ? includeStatus && statusResult.status === "rejected"
          ? "degraded"
          : "ready"
        : resolved.profile
          ? resolved.source === "backend"
            ? "ready"
            : "fallback"
          : "error";
      const nextError =
        !resolved.profile && !backendProfile
          ? "Impossible de determiner le type de cette installation."
          : null;

      return {
        ...current,
        backendProfile,
        lastKnownGoodProfile,
        effectiveProfile: resolved.profile,
        source: resolved.source,
        status: nextStatusValue,
        warning: degradedWarning,
        error: nextError,
        profilePayload: nextProfile,
        installationStatus: nextStatus ?? current.installationStatus,
      };
    });
  }, [packagedProfile, refreshProfile, refreshStatus]);

  useEffect(() => {
    let active = true;
    refresh(false).finally(() => {
      if (!active) {
        return;
      }
    });
    return () => {
      active = false;
    };
  }, [refresh]);

  const mismatchError = detectProfileMismatch(state.backendProfile, state.packagedProfile || packagedProfile);
  const effectiveProfile = state.effectiveProfile;
  const profileStatus = state.status;
  const isCentralServer = isCentralProfile(effectiveProfile);
  const capabilities = state.profilePayload
    ? deriveInstallationCapabilities(state.profilePayload)
    : null;
  const loading = profileStatus === "idle" || profileStatus === "loading";

  const value = useMemo<InstallationProfileContextValue>(
    () => ({
      loading,
      error: state.error,
      status: profileStatus,
      profile: effectiveProfile,
      backendProfile: state.backendProfile,
      packagedProfile: state.packagedProfile,
      source: state.source,
      warning: state.warning,
      profilePayload: state.profilePayload,
      capabilities,
      capabilitiesLoaded: Boolean(state.profilePayload),
      provisioningStatus: String(
        state.installationStatus?.provisioning_status ||
          state.profilePayload?.provisioning_status ||
          "unconfigured",
      ),
      deviceIdentity: deriveDeviceIdentity(state.profilePayload, state.installationStatus),
      installationStatus: state.installationStatus,
      mismatchError,
      refresh,
      refreshProfile,
      refreshStatus,
      isCentralServer,
    }),
    [
      capabilities,
      effectiveProfile,
      isCentralServer,
      loading,
      mismatchError,
      profileStatus,
      refresh,
      refreshProfile,
      refreshStatus,
      state,
    ],
  );

  return <InstallationProfileContext.Provider value={value}>{children}</InstallationProfileContext.Provider>;
};

export const useInstallationProfileContext = () => {
  const context = useContext(InstallationProfileContext);
  if (!context) {
    throw new Error("useInstallationProfileContext must be used within InstallationProfileProvider");
  }
  return context;
};
