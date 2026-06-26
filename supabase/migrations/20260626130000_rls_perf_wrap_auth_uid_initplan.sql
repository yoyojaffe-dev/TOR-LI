-- RLS performance: wrap auth.uid() in (select auth.uid()).
--
-- Per Supabase best practices, a bare auth.uid() in a policy is re-evaluated
-- once PER ROW. Wrapping it as (select auth.uid()) lets Postgres evaluate it
-- once per query (cached as an initplan) — a documented ~100x speedup on large
-- tables. Logic is identical; only evaluation count changes. auth.uid() is also
-- cached inside is_shop_owner. Indexes already exist on every RLS column.

-- helper: cache auth.uid() inside the function
create or replace function public.is_shop_owner(p_shop_id uuid)
returns boolean
language sql
stable
security invoker
set search_path = public
as $$
  select exists (
    select 1 from public.barbershops b
    where b.id = p_shop_id and b.owner_id = (select auth.uid())
  );
$$;

-- users
drop policy if exists users_select_own on public.users;
create policy users_select_own on public.users
  for select to authenticated using ((select auth.uid()) = id);

drop policy if exists users_update_own on public.users;
create policy users_update_own on public.users
  for update to authenticated
  using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

drop policy if exists users_insert_own on public.users;
create policy users_insert_own on public.users
  for insert to authenticated with check ((select auth.uid()) = id);

-- barbershops (owner write)
drop policy if exists barbershops_insert_owner on public.barbershops;
create policy barbershops_insert_owner on public.barbershops
  for insert to authenticated with check (owner_id = (select auth.uid()));

drop policy if exists barbershops_update_owner on public.barbershops;
create policy barbershops_update_owner on public.barbershops
  for update to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));

-- appointments (client own)
drop policy if exists appointments_select_own_client on public.appointments;
create policy appointments_select_own_client on public.appointments
  for select to authenticated using ((select auth.uid()) = client_id);

drop policy if exists appointments_insert_own_client on public.appointments;
create policy appointments_insert_own_client on public.appointments
  for insert to authenticated with check ((select auth.uid()) = client_id);

-- NOTE: services / staff / available_slots owner policies call is_shop_owner()
-- with a per-row column (shop_id / barbershop_id), so they cannot be initplan-
-- cached; the auth.uid() caching inside the function is the applicable win.
