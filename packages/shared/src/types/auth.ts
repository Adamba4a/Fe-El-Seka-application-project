export interface OtpRequest {
  email: string;
}

export interface OtpVerifyRequest {
  email: string;
  otp: string;
}

export interface SessionUser {
  id: string;
  email: string;
  is_new_user: boolean;
}

export interface SessionResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: SessionUser;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface PasswordSignInRequest {
  email: string;
  password: string;
}

export interface SetPasswordRequest {
  new_password: string;
}

export interface AdminLoginRequest {
  email: string;
  password: string;
}
