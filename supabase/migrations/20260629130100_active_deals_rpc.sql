-- Deals are time-limited promotions worth travelling for, so they must NOT be
-- distance-gated like the quick-book nearby feed (that capped them out of range —
-- e.g. a Tel-Aviv deal never reached a Jerusalem-default consumer). active_deals
-- returns ALL currently-bookable deals (free, future, unblocked, active
-- staff+service), ordered nearest-first for relevance but with no radius cap.
create or replace function public.active_deals(p_lat double precision, p_lng double precision)
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
        st_distance(bs.location, st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography) as distance_m,
        s.is_deal, s.deal_price
    from public.available_slots s
    join public.barbershops bs on bs.id = s.barbershop_id
    where s.is_deal = true
      and s.status = 'free'
      and s.slot_time >= now()
      and not public.is_slot_blocked(s.id)
      and (s.staff_id is null
           or exists (select 1 from public.staff st where st.id = s.staff_id and st.is_active))
      and not exists (select 1 from public.services sv
                      where sv.shop_id = s.barbershop_id
                        and sv.name = s.service_name
                        and (sv.is_active = false or sv.deleted_at is not null))
      and bs.location is not null
    order by distance_m asc, s.slot_time asc
    limit 50;
$$;
grant execute on function public.active_deals(double precision, double precision)
  to anon, authenticated, service_role;
