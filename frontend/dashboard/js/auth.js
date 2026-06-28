// Barber auth: login via Supabase Auth; signup via the dev-only backend endpoint
// (creates a PRE-CONFIRMED account so onboarding works without an email inbox).
import { supabase } from "./supabaseClient.js";
import { config } from "./config.js";

export async function getSession() {
  const { data } = await supabase.auth.getSession();
  return data.session;
}

export function onAuthChange(cb) {
  return supabase.auth.onAuthStateChange((_event, session) => cb(session));
}

export function signIn(email, password) {
  return supabase.auth.signInWithPassword({ email, password });
}

export function signOut() {
  return supabase.auth.signOut();
}

// Create a pre-confirmed barber account through the backend, then sign in.
export async function signUp(email, password, fullName, phone) {
  const res = await fetch(`${config.BACKEND_URL}/admin/barber-signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName, phone }),
  });
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch { detail = res.statusText; }
    throw new Error(detail || "signup failed");
  }
  return signIn(email, password);
}
