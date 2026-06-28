-- Let a shop owner read the consumer bookings for their shop. Consumer bookings
-- persist to public.bookings (customer_name/phone); the original owner RLS was on
-- the (empty) appointments table, so owners couldn't see real bookings. Applied to
-- the live project via the Supabase MCP; recorded here to keep repo and DB in sync.

alter table public.bookings enable row level security;

drop policy if exists "bookings select shop owner" on public.bookings;
create policy "bookings select shop owner"
  on public.bookings for select to authenticated
  using (
    exists (
      select 1
      from public.available_slots s
      join public.barbershops b on b.id = s.barbershop_id
      where s.id = bookings.slot_id
        and b.owner_id = auth.uid()
    )
  );

grant select on public.bookings to authenticated;
