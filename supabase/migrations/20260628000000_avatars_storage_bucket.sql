-- Public Storage bucket for consumer profile pictures.
-- Auth is not wired, so the anon role uploads files keyed by the app's
-- per-browser user_token (e.g. avatars/<user_token>.jpg). Applied to the live
-- project via the Supabase MCP; recorded here to keep repo and DB in sync.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('avatars', 'avatars', true, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

drop policy if exists "avatars anon read" on storage.objects;
create policy "avatars anon read"
  on storage.objects for select to anon
  using (bucket_id = 'avatars');

drop policy if exists "avatars anon insert" on storage.objects;
create policy "avatars anon insert"
  on storage.objects for insert to anon
  with check (bucket_id = 'avatars');

drop policy if exists "avatars anon update" on storage.objects;
create policy "avatars anon update"
  on storage.objects for update to anon
  using (bucket_id = 'avatars')
  with check (bucket_id = 'avatars');
