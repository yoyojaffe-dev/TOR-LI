-- SECURITY + LOGIC hardening from the pre-production audit (M1, L2, L3, P2.1).

-- M1: public.spatial_ref_sys (PostGIS) had RLS disabled AND anon INSERT/UPDATE/
-- DELETE grants — an attacker could corrupt/delete SRID rows (e.g. 4326) and
-- break every geo/radius query (DoS). It is read-only reference data; revoke
-- all anon/authenticated writes.
revoke insert, update, delete on table public.spatial_ref_sys from anon, authenticated;

-- L2: availability_overrides was anon-readable (USING true), exposing every
-- shop's blocked dates + free-text notes. The consumer never reads this table
-- directly (free_slots / is_slot_blocked are SECURITY DEFINER), so restrict
-- reads to the owner. The existing "overrides owner write" policy is FOR ALL,
-- so authenticated owners keep SELECT on their own rows.
drop policy if exists "overrides read" on public.availability_overrides;
revoke select on public.availability_overrides from anon;

-- L3: pin search_path on the older geo SECURITY DEFINER function(s) flagged by
-- the linter (function_search_path_mutable).
do $$
declare r record;
begin
  for r in
    select p.oid::regprocedure as sig from pg_proc p
    where p.pronamespace = 'public'::regnamespace and p.proname = 'barbershops_within_radius'
  loop
    execute format('alter function %s set search_path = public', r.sig);
  end loop;
end $$;

-- P2.1: free_slots must hide slots whose assigned staff member is INACTIVE or
-- whose named service is INACTIVE, so deactivating staff/services is consistent
-- between the consumer service menu and the bookable-slots feed.
create or replace function public.free_slots(p_barbershop_id uuid)
returns setof public.available_slots
language sql stable security definer set search_path = public as $$
  select s.*
  from public.available_slots s
  where s.barbershop_id = p_barbershop_id
    and s.status = 'free'
    and s.slot_time > now()
    and not public.is_slot_blocked(s.id)
    and (s.staff_id is null
         or exists (select 1 from public.staff st
                    where st.id = s.staff_id and st.is_active))
    and not exists (select 1 from public.services sv
                    where sv.shop_id = s.barbershop_id
                      and sv.name = s.service_name
                      and sv.is_active = false)
  order by s.slot_time;
$$;
