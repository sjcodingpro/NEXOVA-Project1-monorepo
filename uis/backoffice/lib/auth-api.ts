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

export interface MessageResponse {
  message: string;
}

export function forgotPassword(email: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, new_password: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password }),
  });
}

export function changePassword(
  current_password: string,
  new_password: string
): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password, new_password }),
  });
}
