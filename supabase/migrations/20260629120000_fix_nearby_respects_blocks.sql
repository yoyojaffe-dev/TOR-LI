-- The consumer nearby/deals feed must respect availability blocks. free_slots()
-- already calls is_slot_blocked(), but available_slots_nearby() only checked
-- status='free', so blocked times leaked into the home feed (and were quick-
-- bookable until lock_slot rejected them). Add the same guard.
create or replace function public.available_slots_nearby(
    lat double precision,
    lng double precision,
    radius_m integer default 5000,
    lim integer default 20
)
returns table(
    slot_id uuid,
    slot_time timestamptz,
    service_name text,
    price numeric,
    barbershop_id uuid,
    shop_name text,
    shop_address text,
    lat_out double precision,
    lng_out double precision,
    distance_m double precision,
    is_deal boolean,
    deal_price numeric
)
language sql
stable
set search_path to 'public'
as $$
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
      and bs.location is not null
      and bs.place_type in ('barber_shop', 'hair_care')
      and st_dwithin(bs.location, st_setsrid(st_makepoint(lng, lat), 4326)::geography, radius_m)
    order by distance_m asc, s.slot_time asc
    limit lim;
$$;
grant execute on function public.available_slots_nearby(double precision, double precision, integer, integer)
  to anon, authenticated, service_role;
