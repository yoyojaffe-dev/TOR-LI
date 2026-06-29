-- "90th-minute" Last-Minute Deals: a barber can flag an upcoming free slot as a
-- deal and optionally set a discounted price; the consumer highlights these.
alter table public.available_slots
  add column if not exists is_deal boolean not null default false,
  add column if not exists deal_price numeric;

-- free_slots() returns SETOF available_slots, so it picks up the new columns
-- automatically. The nearby feed has an explicit RETURNS TABLE, so extend it
-- (drop first — Postgres can't change a function's return type in place).
drop function if exists public.available_slots_nearby(double precision, double precision, integer, integer);
create function public.available_slots_nearby(
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
      and bs.location is not null
      and bs.place_type in ('barber_shop', 'hair_care')
      and st_dwithin(bs.location, st_setsrid(st_makepoint(lng, lat), 4326)::geography, radius_m)
    order by distance_m asc, s.slot_time asc
    limit lim;
$$;
grant execute on function public.available_slots_nearby(double precision, double precision, integer, integer)
  to anon, authenticated, service_role;
