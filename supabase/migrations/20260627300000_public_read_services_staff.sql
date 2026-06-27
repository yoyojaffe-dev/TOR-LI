-- Public read for services + staff so the anonymous consumer app can show the
-- shop menu and team (same posture as barbershops). Owner write policies are
-- unchanged; only SELECT is opened to anon.

-- services: replace the authenticated-only SELECT with public read.
drop policy if exists "services_select_authenticated" on public.services;
drop policy if exists "services public read" on public.services;
create policy "services public read"
    on public.services for select
    to anon, authenticated
    using (true);

grant select on public.services to anon;

-- staff: same.
drop policy if exists "staff_select_authenticated" on public.staff;
drop policy if exists "staff public read" on public.staff;
create policy "staff public read"
    on public.staff for select
    to anon, authenticated
    using (true);

grant select on public.staff to anon;
