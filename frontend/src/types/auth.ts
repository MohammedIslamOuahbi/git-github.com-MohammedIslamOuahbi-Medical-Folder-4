import type { Role } from "./common";

export interface LoginPayload {
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

export interface AuthUser {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  role: Role;
  role_code?: "super_admin" | "admin" | "doctor" | "assistant" | null;
  company_id?: number | null;
  branch_id?: number | null;
  avatar_url?: string | null;
  signature_png?: string | null;
  signatureUrl?: string | null;
  signature_url?: string | null;
  signaturePngUrl?: string | null;
  signature_png_url?: string | null;
  signaturePath?: string | null;
  signature_path?: string | null;
  signatureImageUrl?: string | null;
  hasSignature?: boolean;
  signatureUploadedAt?: string | null;
  permissions?: string[];
  permissions_version?: number;
}

export interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
}
