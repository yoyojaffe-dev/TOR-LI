-- Tor-li RLS policies + SECURITY DEFINER on mutation RPCs.
--
-- Frontend + backend both use the anon key. With RLS enabled and no policies,
-- every read/write is blocked. We allow public READ of discovery data
-- (barbershops, available_slots) so the catalog + Realtime work, keep direct
-- writes closed, and route all mutations through SECURITY DEFINER RPCs that run
-- as the function owner (bypassing RLS in a controlled way).

-- --- Public read access (anon) ---
do $$ begin
    create policy "public read barbershops"
        on public.barbershops for select
        to anon, authenticated using (true);
exception when duplicate_object then null; end $$;

do $$ begin
    create policy "public read available_slots"
        on public.available_slots for select
        to anon, authenticated using (true);
exception when duplicate_object then null; end $$;

-- bookings: no anon SELECT policy (kept private). Inserts happen via RPC.

-- --- Controlled mutations bypass RLS via SECURITY DEFINER ---
alter function public.lock_slot(uuid, text, integer)      security definer set search_path = public;
alter function public.release_slot(uuid, text)            security definer set search_path = public;
alter function public.confirm_booking(uuid, text, uuid)   security definer set search_path = public;
alter function public.upsert_barbershop(text, double precision, double precision, text, text, text, text)
    security definer set search_path = public;
