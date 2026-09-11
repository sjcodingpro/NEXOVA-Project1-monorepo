import { apiFetch } from "@/lib/api-client";

export interface RegisterPayload {
  email: string;
  password: string;
  name?: string;
  phone?: string;
  address?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface ProfileData {
  id: number;
  user_id: number;
  name: string | null;
  phone: string | null;
  address: string | null;
}

export interface MeResponse {
  id: number;
  email: string;
  role: string;
  profile: ProfileData | null;
}

export interface UserResponse {
  id: number;
  email: string;
  is_active: boolean;
  role: string;
  created_at: string;
}

export function registerUser(payload: RegisterPayload): Promise<UserResponse> {
  return apiFetch<UserResponse>("/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function login(payload: LoginPayload): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/auth/me");
}

export function updateMyProfile(payload: {
  name?: string;
  phone?: string;
  address?: string;
}): Promise<ProfileData> {
  return apiFetch<ProfileData>("/profiles/me", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
