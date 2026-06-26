-- User-submitted reviews + a "free slots nearby" RPC for home quick-book.

-- Reviews are tied to a completed booking (one review per booking).
create table if not exists public.reviews (
    id            uuid primary key default gen_random_uuid(),
    booking_id    uuid not null references public.bookings(id) on delete cascade,
    barbershop_id uuid not null references public.barbershops(id) on delete cascade,
    user_token    text not null,
    rating        int  not null check (rating between 1 and 5),
    comment       text,
    created_at    timestamptz not null default now(),
    unique (booking_id)
);
create index if not exists reviews_barbershop_idx on public.reviews (barbershop_id);

-- Submit (or update) a review. Validates the booking belongs to the user.
create or replace function public.submit_review(
    p_booking_id uuid,
    p_user       text,
    p_rating     int,
    p_comment    text default null
)
returns table(success boolean, message text)
language plpgsql
security definer
set search_path to 'public'
as $$
declare
    v_shop uuid;
begin
    select bs.id into v_shop
    from public.bookings b
    join public.available_slots s on s.id = b.slot_id
    join public.barbershops bs on bs.id = s.barbershop_id
    where b.id = p_booking_id and b.user_token = p_user;

    if v_shop is null then
        return query select false, 'booking not found for this user'::text;
        return;
    end if;
    if p_rating < 1 or p_rating > 5 then
        return query select false, 'rating must be 1-5'::text;
        return;
    end if;

    insert into public.reviews (booking_id, barbershop_id, user_token, rating, comment)
    values (p_booking_id, v_shop, p_user, p_rating, p_comment)
    on conflict (booking_id) do update
        set rating = excluded.rating, comment = excluded.comment, created_at = now();

    return query select true, 'saved'::text;
end;
$$;

grant execute on function public.submit_review(uuid, text, int, text) to anon, authenticated, service_role;

-- Recent reviews for a barbershop (most recent first), with a masked display name.
create or replace function public.reviews_for_barbershop(p_shop uuid)
returns table(
    id uuid,
    rating int,
    comment text,
    created_at timestamptz,
    display_name text
)
language sql
security definer
set search_path to 'public'
as $$
    select r.id, r.rating, r.comment, r.created_at,
           coalesce(left(b.customer_name, 1) || '.', 'אורח') as display_name
    from public.reviews r
    join public.bookings b on b.id = r.booking_id
    where r.barbershop_id = p_shop
    order by r.created_at desc
    limit 50;
$$;

grant execute on function public.reviews_for_barbershop(uuid) to anon, authenticated, service_role;

-- Free upcoming slots near a point, joined to shop info (home "Available Nearby").
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
    distance_m double precision
)
language sql
stable
set search_path to 'public'
as $$
    select
        s.id, s.slot_time, s.service_name, s.price,
        bs.id, bs.name, bs.address,
        st_y(bs.location::geometry), st_x(bs.location::geometry),
        st_distance(bs.location, st_setsrid(st_makepoint(lng, lat), 4326)::geography) as distance_m
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

grant execute on function public.available_slots_nearby(double precision, double precision, integer, integer) to anon, authenticated, service_role;
