-- Table-level privileges for anon + authenticated (RLS alone is not enough in newer Supabase projects).
grant usage on schema public to anon, authenticated;
grant select on public.barbershops     to anon, authenticated;
grant select on public.available_slots to anon, authenticated;
-- bookings: intentionally no anon SELECT (private).

-- Also make barbershops_within_radius SECURITY DEFINER so it can read the
-- PostGIS spatial reference table regardless of the caller's role.
alter function public.barbershops_within_radius(double precision, double precision, integer)
    security definer set search_path = public;
