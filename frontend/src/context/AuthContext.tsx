import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import axios from "axios";
import { authApi } from "@/api/authApi";
import { connectionModeApi } from "@/services/connectionModeApi";
import type { AuthState, AuthUser, LoginPayload } from "@/types/auth";
import { tokenStorage, userStorage } from "@/utils/storage";

interface AuthContextValue extends AuthState {
  loading: boolean;
  hasStoredSession: boolean;
  profileResolved: boolean;
  profileWarning: string | null;
  login: (payload: LoginPayload) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

export class AuthProfileFetchError extends Error {
  constructor(message = "AUTH_PROFILE_FETCH_FAILED") {
    super(message);
    this.name = "AuthProfileFetchError";
  }
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const initialUser = userStorage.get<AuthUser>();
let sharedProfileBootstrapPromise: Promise<AuthUser> | null = null;
let sharedProfileBootstrapToken: string | null = null;

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(initialUser);
  const [loading, setLoading] = useState(true);
  const [profileResolved, setProfileResolved] = useState(!tokenStorage.getAccessToken());
  const [profileWarning, setProfileWarning] = useState<string | null>(null);
  const [tokens, setTokens] = useState({
    accessToken: tokenStorage.getAccessToken(),
    refreshToken: tokenStorage.getRefreshToken(),
  });

  const clearSession = useCallback(() => {
    tokenStorage.clear();
    userStorage.clear();
    setUser(null);
    setTokens({ accessToken: null, refreshToken: null });
    setProfileResolved(true);
    setProfileWarning(null);
  }, []);

  const refreshProfile = useCallback(async () => {
    const accessToken = tokenStorage.getAccessToken();
    if (!accessToken) {
      setProfileResolved(true);
      setProfileWarning(null);
      return;
    }

    setProfileResolved(false);
    setProfileWarning(null);

    if (!sharedProfileBootstrapPromise || sharedProfileBootstrapToken !== accessToken) {
      sharedProfileBootstrapToken = accessToken;
      sharedProfileBootstrapPromise = authApi.me().finally(() => {
        sharedProfileBootstrapPromise = null;
        sharedProfileBootstrapToken = null;
      });
    }

    try {
      const profile = await sharedProfileBootstrapPromise;
      setUser(profile);
      userStorage.set(profile);
      setProfileResolved(true);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        clearSession();
        return;
      }

      setProfileResolved(true);
      setProfileWarning("Le profil utilisateur n'a pas pu etre actualise. Reessayez dans quelques instants.");
      if (!userStorage.get<AuthUser>()) {
        setUser((current) => current);
      }
      throw error;
    }
  }, [clearSession]);

  useEffect(() => {
    const run = async () => {
      if (!tokens.accessToken) {
        setProfileResolved(true);
        setLoading(false);
        return;
      }

      setLoading(true);
      if (tokens.accessToken) {
        try {
          await refreshProfile();
        } catch {
          // Non-auth failures leave the existing session intact.
        }
      }
      setLoading(false);
    };
    void run();
  }, [refreshProfile, tokens.accessToken]);

  const login = useCallback(async (payload: LoginPayload) => {
    const tokenPair = await authApi.login(payload);
    tokenStorage.setTokens(tokenPair.access_token, tokenPair.refresh_token);
    setTokens({
      accessToken: tokenPair.access_token,
      refreshToken: tokenPair.refresh_token,
    });
    setProfileResolved(false);
    setProfileWarning(null);
    try {
      const profile = await authApi.me();
      await connectionModeApi.synchronizeLocalBackendMode(profile.permissions);
      setUser(profile);
      userStorage.set(profile);
      setProfileResolved(true);
      return profile;
    } catch (error) {
      clearSession();
      throw new AuthProfileFetchError(
        error instanceof Error ? error.message : "AUTH_PROFILE_FETCH_FAILED",
      );
    }
  }, [clearSession]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Intentionally ignored to allow local logout on API failure.
    }
    clearSession();
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      isAuthenticated: Boolean(tokens.accessToken && user),
      loading,
      hasStoredSession: Boolean(tokens.accessToken),
      profileResolved,
      profileWarning,
      login,
      logout,
      refreshProfile,
    }),
    [
      loading,
      login,
      logout,
      profileResolved,
      profileWarning,
      refreshProfile,
      tokens.accessToken,
      tokens.refreshToken,
      user,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};
