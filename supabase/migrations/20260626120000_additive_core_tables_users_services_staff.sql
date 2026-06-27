-- Additive core tables: users, services, staff
-- + barbershops.is_active_partner, GiST spatial index.
--
-- Discovery: the live DB already runs barbershops / available_slots / bookings
-- under app-specific names. This migration is ADDITIVE only — it does NOT rename
-- or restructure existing tables, so the running backend/frontend keep working.
-- available_slots / bookings are intentionally left untouched.

-- PostGIS already installed (3.3.7); no-op safety.
create extension if not exists postgis;

-- ---------------------------------------------------------------------
-- 1. users  (profiles coupled to Supabase auth.users)
-- ---------------------------------------------------------------------
create table if not exists public.users (
  id         uuid primary key references auth.users (id) on delete cascade,
  role       text not null check (role in ('client', 'barber', 'owner')),
  full_name  text,
  phone      text,
  created_at timestamptz not null default now()
);

alter table public.users enable row level security;

do $$ begin
  create policy users_select_own on public.users
    for select to authenticated using (auth.uid() = id);
exception when duplicate_object then null; end $$;

do $$ begin
  create policy users_update_own on public.users
    for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);
exception when duplicate_object then null; end $$;

-- insert own profile (needed so an authenticated user can create their row;
-- remove if a trigger on auth.users creates profiles instead).
do $$ begin
  create policy users_insert_own on public.users
    for insert to authenticated with check (auth.uid() = id);
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- 2. barbershops (existing) — add missing column + spatial index
-- ---------------------------------------------------------------------
alter table public.barbershops
  add column if not exists is_active_partner boolean not null default false;

-- GiST index for fast PostGIS radial queries already exists from init
-- (barbershops_location_gix) — no new index needed here.

-- ---------------------------------------------------------------------
-- 3. services  (catalog per shop)
-- ---------------------------------------------------------------------
create table if not exists public.services (
  id            uuid primary key default gen_random_uuid(),
  shop_id       uuid not null references public.barbershops (id) on delete cascade,
  name          text not null,
  duration_mins integer not null default 30,
  price         integer not null
);

create index if not exists idx_services_shop_id on public.services (shop_id);

alter table public.services enable row level security;

do $$ begin
  create policy services_select_authenticated on public.services
    for select to authenticated using (true);
exception when duplicate_object then null; end $$;

-- Owner-scoped write policies are added in the next migration, once the
-- ownership link (barbershops.owner_id) exists.

-- ---------------------------------------------------------------------
-- 4. staff  (employees per shop)
-- ---------------------------------------------------------------------
create table if not exists public.staff (
  id        uuid primary key default gen_random_uuid(),
  shop_id   uuid not null references public.barbershops (id) on delete cascade,
  name      text not null,
  is_active boolean not null default true
);

create index if not exists idx_staff_shop_id on public.staff (shop_id);

alter table public.staff enable row level security;

do $$ begin
  create policy staff_select_authenticated on public.staff
    for select to authenticated using (true);
exception when duplicate_object then null; end $$;
