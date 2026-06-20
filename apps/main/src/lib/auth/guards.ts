import { redirect } from "next/navigation";
import { createClient } from "../supabase/server";
import type { Role } from "@fe-el-seka/shared";

export async function requireAuth(): Promise<string> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) redirect("/login");
  return session.access_token;
}

export async function requireRole(expected: Role): Promise<string> {
  const token = await requireAuth();
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .single();

  if (!profile || profile.role !== expected) redirect("/");
  return token;
}
