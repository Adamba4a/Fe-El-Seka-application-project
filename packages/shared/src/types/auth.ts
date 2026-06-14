export interface OtpRequest {
  phone_number: string;
}

export interface OtpVerifyRequest {
  phone_number: string;
  otp: string;
}

export interface SessionUser {
  id: string;
  phone_number: string;
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

export interface AdminLoginRequest {
  email: string;
  password: string;
}
