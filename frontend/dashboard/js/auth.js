// Barber auth: login via Supabase Auth; signup via the dev-only backend endpoint
// (creates a PRE-CONFIRMED account so onboarding works without an email inbox).
import { supabase } from "./supabaseClient.js";
import { config } from "./config.js";

export async function getSession() {
  const { data } = await supabase.auth.getSession();
  return data.session;
}

export function onAuthChange(cb) {
  // Expose the event type (SIGNED_IN / SIGNED_OUT / TOKEN_REFRESHED / …) so the
  // caller can distinguish a real session change from a routine token refresh.
  return supabase.auth.onAuthStateChange((event, session) => cb(event, session));
}

export function signIn(email, password) {
  return supabase.auth.signInWithPassword({ email, password });
}

export function signOut() {
  return supabase.auth.signOut();
}

export async function currentEmail() {
  const { data } = await supabase.auth.getUser();
  return data.user?.email;
}

// Re-authenticate the current user (required before sensitive account changes).
// Throws if the supplied current password is wrong.
export async function reauthenticate(currentPassword) {
  const email = await currentEmail();
  if (!email) throw new Error("לא מחובר");
  const { error } = await supabase.auth.signInWithPassword({ email, password: currentPassword });
  if (error) throw new Error("הסיסמה הנוכחית שגויה");
}

// Change password — caller must re-authenticate first.
export async function updatePassword(newPassword) {
  const { error } = await supabase.auth.updateUser({ password: newPassword });
  if (error) throw new Error(error.message || "עדכון הסיסמה נכשל");
}

// Change email — caller must re-authenticate first.
export async function updateEmail(newEmail) {
  const { error } = await supabase.auth.updateUser({ email: newEmail });
  if (error) throw new Error(error.message || "עדכון האימייל נכשל");
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
