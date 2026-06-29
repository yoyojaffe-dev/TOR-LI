// Profile-picture uploads to the public Supabase Storage `avatars` bucket.
// Files are keyed by the per-browser device id (decoupled from auth so uploads
// work before login).
import { supabase } from "./supabaseClient.js";

// Upload `file` and return its public URL (cache-busted so re-uploads to the
// same key refresh the <img>). Throws on failure — callers fall back to a local
// data-URL so the picker never hard-fails.
export async function uploadAvatar(file, deviceId) {
  const ext = file.type === "image/png" ? "png" : file.type === "image/webp" ? "webp" : "jpg";
  const key = `${deviceId}.${ext}`;
  const { error } = await supabase.storage.from("avatars").upload(key, file, {
    upsert: true,
    contentType: file.type || "image/jpeg",
  });
  if (error) throw error;
  const { data } = supabase.storage.from("avatars").getPublicUrl(key);
  return `${data.publicUrl}?t=${Date.now()}`;
}
