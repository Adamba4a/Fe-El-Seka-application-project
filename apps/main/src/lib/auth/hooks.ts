"use client";

import { useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import type { Role } from "@fe-el-seka/shared";
import { createClient } from "../supabase/client";

// Single shared client instance — createBrowserClient is designed as a singleton
// in browser contexts. Creating one per hook call leaks auth subscriptions.
const supabase = createClient();

export function useSession() {
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => listener.subscription.unsubscribe();
  }, []);

  return session;
}

export function useUser(): User | null {
  const session = useSession();
  return session?.user ?? null;
}

export function useRole(): Role | null {
  const [role, setRole] = useState<Role | null>(null);
  const session = useSession();

  useEffect(() => {
    if (!session?.user) { setRole(null); return; }
    supabase
      .from("profiles")
      .select("role")
      .eq("id", session.user.id)
      .single()
      .then(({ data }) => setRole((data?.role as Role) ?? null));
  }, [session]);

  return role;
}
