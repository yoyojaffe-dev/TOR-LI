-- Owner-scoped writes + appointments table.
--   * barbershops.owner_id          ownership link -> public.users
--   * is_shop_owner(uuid)           ownership predicate used by RLS
--   * owner write policies          services / staff / available_slots / barbershops
--   * available_slots.staff_id      spec column (additive; barbershop_id kept)
--   * appointments                  spec-compliant booking table, parallel to bookings
-- All additive. Existing app (service_role / SECURITY DEFINER RPCs) unaffected.

-- ---------------------------------------------------------------------
-- Ownership link
-- ---------------------------------------------------------------------
alter table public.barbershops
  add column if not exists owner_id uuid references public.users (id) on delete set null;

create index if not exists idx_barbershops_owner_id on public.barbershops (owner_id);

-- Ownership predicate used by RLS policies below.
-- (Hardened to SECURITY INVOKER + restricted EXECUTE in the next migration.)
create or replace function public.is_shop_owner(p_shop_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.barbershops b
    where b.id = p_shop_id and b.owner_id = auth.uid()
  );
$$;

-- ---------------------------------------------------------------------
-- barbershops: owner insert/update (service_role/RPCs still bypass RLS)
-- ---------------------------------------------------------------------
do $$ begin
  create policy barbershops_insert_owner on public.barbershops
    for insert to authenticated with check (owner_id = auth.uid());
exception when duplicate_object then null; end $$;

do $$ begin
  create policy barbershops_update_owner on public.barbershops
    for update to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- services: owner-scoped INSERT / UPDATE / DELETE
-- ---------------------------------------------------------------------
do $$ begin
  create policy services_insert_owner on public.services
    for insert to authenticated with check (public.is_shop_owner(shop_id));
exception when duplicate_object then null; end $$;

do $$ begin
  create policy services_update_owner on public.services
    for update to authenticated using (public.is_shop_owner(shop_id)) with check (public.is_shop_owner(shop_id));
exception when duplicate_object then null; end $$;

do $$ begin
  create policy services_delete_owner on public.services
    for delete to authenticated using (public.is_shop_owner(shop_id));
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- staff: owner-scoped write
-- ---------------------------------------------------------------------
do $$ begin
  create policy staff_insert_owner on public.staff
    for insert to authenticated with check (public.is_shop_owner(shop_id));
exception when duplicate_object then null; end $$;

do $$ begin
  create policy staff_update_owner on public.staff
    for update to authenticated using (public.is_shop_owner(shop_id)) with check (public.is_shop_owner(shop_id));
exception when duplicate_object then null; end $$;

do $$ begin
  create policy staff_delete_owner on public.staff
    for delete to authenticated using (public.is_shop_owner(shop_id));
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- available_slots: add staff_id (spec) + owner write policies
-- (column is barbershop_id in this DB; left as-is per additive choice)
-- ---------------------------------------------------------------------
alter table public.available_slots
  add column if not exists staff_id uuid references public.staff (id) on delete set null;

create index if not exists idx_available_slots_staff_id on public.available_slots (staff_id);

do $$ begin
  create policy available_slots_insert_owner on public.available_slots
    for insert to authenticated with check (public.is_shop_owner(barbershop_id));
exception when duplicate_object then null; end $$;

do $$ begin
  create policy available_slots_update_owner on public.available_slots
    for update to authenticated using (public.is_shop_owner(barbershop_id)) with check (public.is_shop_owner(barbershop_id));
exception when duplicate_object then null; end $$;

do $$ begin
  create policy available_slots_delete_owner on public.available_slots
    for delete to authenticated using (public.is_shop_owner(barbershop_id));
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- appointments (spec-compliant; parallel to existing bookings)
-- ---------------------------------------------------------------------
create table if not exists public.appointments (
  id           uuid primary key default gen_random_uuid(),
  client_id    uuid not null references public.users (id) on delete cascade,
  slot_id      uuid not null unique references public.available_slots (id) on delete cascade,
  status       text not null default 'pending'
               check (status in ('pending', 'confirmed', 'completed', 'cancelled')),
  client_notes text,
  locked_until timestamptz,
  created_at   timestamptz not null default now()
);

create index if not exists idx_appointments_client_id on public.appointments (client_id);

alter table public.appointments enable row level security;

-- clients: read + insert only their own rows
do $$ begin
  create policy appointments_select_own_client on public.appointments
    for select to authenticated using (auth.uid() = client_id);
exception when duplicate_object then null; end $$;

do $$ begin
  create policy appointments_insert_own_client on public.appointments
    for insert to authenticated with check (auth.uid() = client_id);
exception when duplicate_object then null; end $$;

-- shop owners: read appointments for slots in their shop
do $$ begin
  create policy appointments_select_shop_owner on public.appointments
    for select to authenticated using (
      exists (
        select 1 from public.available_slots s
        where s.id = appointments.slot_id
          and public.is_shop_owner(s.barbershop_id)
      )
    );
exception when duplicate_object then null; end $$;
