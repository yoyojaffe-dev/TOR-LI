-- Sync fix: a removed service must stop being bookable EVERYWHERE (consumer
-- profile via free_slots AND the home/nearby feed via available_slots_nearby).
--
-- Two gaps were leaking removed-service slots to consumers:
--   1. available_slots_nearby had no active-service / active-staff filter at all.
--   2. Hard-deleting a service left its row gone, so the name-match filter in
--      free_slots could not catch the orphaned slots.
-- Fix: soft-delete services (deleted_at) so the row persists for the filters, and
-- apply the same active-staff + active/non-deleted-service guards in both RPCs.

alter table public.services add column if not exists deleted_at timestamptz;

-- free_slots: also exclude soft-deleted services.
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
         or exists (select 1 from public.staff st where st.id = s.staff_id and st.is_active))
    and not exists (select 1 from public.services sv
                    where sv.shop_id = s.barbershop_id
                      and sv.name = s.service_name
                      and (sv.is_active = false or sv.deleted_at is not null))
  order by s.slot_time;
$$;

-- available_slots_nearby: mirror free_slots' active-staff + active-service guards
-- (it previously filtered only status + block).
create or replace function public.available_slots_nearby(
    lat double precision,
    lng double precision,
    radius_m integer default 5000,
    lim integer default 20
)
returns table(
    slot_id uuid, slot_time timestamptz, service_name text, price numeric,
    barbershop_id uuid, shop_name text, shop_address text,
    lat_out double precision, lng_out double precision, distance_m double precision,
    is_deal boolean, deal_price numeric
)
language sql stable set search_path to 'public' as $$
    select
        s.id, s.slot_time, s.service_name, s.price,
        bs.id, bs.name, bs.address,
        st_y(bs.location::geometry), st_x(bs.location::geometry),
        st_distance(bs.location, st_setsrid(st_makepoint(lng, lat), 4326)::geography) as distance_m,
        s.is_deal, s.deal_price
    from public.available_slots s
    join public.barbershops bs on bs.id = s.barbershop_id
    where s.status = 'free'
      and s.slot_time >= now()
      and not public.is_slot_blocked(s.id)
      and (s.staff_id is null
           or exists (select 1 from public.staff st where st.id = s.staff_id and st.is_active))
      and not exists (select 1 from public.services sv
                      where sv.shop_id = s.barbershop_id
                        and sv.name = s.service_name
                        and (sv.is_active = false or sv.deleted_at is not null))
      and bs.location is not null
      and bs.place_type in ('barber_shop', 'hair_care')
      and st_dwithin(bs.location, st_setsrid(st_makepoint(lng, lat), 4326)::geography, radius_m)
    order by distance_m asc, s.slot_time asc
    limit lim;
$$;
grant execute on function public.available_slots_nearby(double precision, double precision, integer, integer)
  to anon, authenticated, service_role;
-- (Pre-existing orphan slots from earlier hard-deletes are cleaned up as a
-- separate, verified data step — not in this migration — to avoid deleting
-- legitimately-named seeded slots.)
