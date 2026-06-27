-- Add booking_platform to barbershops so the Booking Agent can route to a
-- platform-specific adapter (tor4you / glamera / booksy / custom). Recorded at
-- discovery time from the booking_url; "custom" means use the AI fallback.

alter table public.barbershops add column if not exists booking_platform text;

-- Rebuild upsert_barbershop with the new p_booking_platform param.
create or replace function public.upsert_barbershop(
    p_name             text,
    p_lat              double precision,
    p_lng              double precision,
    p_address          text default null,
    p_phone            text default null,
    p_booking_url      text default null,
    p_google_place_id  text default null,
    p_photo_url        text default null,
    p_place_type       text default 'barber_shop',
    p_photo_urls       jsonb default '[]'::jsonb,
    p_rating           numeric default null,
    p_rating_count     int default null,
    p_booking_platform text default null
)
returns uuid
language plpgsql
security definer
set search_path to 'public'
as $$
declare
    v_id uuid;
begin
    insert into public.barbershops
        (name, address, phone, booking_url, google_place_id, location,
         photo_url, place_type, photo_urls, rating, rating_count, booking_platform)
    values (
        p_name, p_address, p_phone, p_booking_url, p_google_place_id,
        st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography,
        p_photo_url, p_place_type, p_photo_urls, p_rating, p_rating_count, p_booking_platform
    )
    on conflict (google_place_id) do update
        set name             = excluded.name,
            address          = excluded.address,
            phone            = excluded.phone,
            booking_url      = excluded.booking_url,
            location         = excluded.location,
            photo_url        = coalesce(excluded.photo_url, public.barbershops.photo_url),
            place_type       = coalesce(excluded.place_type, public.barbershops.place_type),
            photo_urls       = case when jsonb_array_length(excluded.photo_urls) > 0
                                    then excluded.photo_urls
                                    else public.barbershops.photo_urls end,
            rating           = coalesce(excluded.rating, public.barbershops.rating),
            rating_count     = coalesce(excluded.rating_count, public.barbershops.rating_count),
            booking_platform = coalesce(excluded.booking_platform, public.barbershops.booking_platform)
    returning id into v_id;
    return v_id;
end;
$$;

grant execute on function public.upsert_barbershop(text, double precision, double precision, text, text, text, text, text, text, jsonb, numeric, int, text)
    to anon, authenticated, service_role;

-- Surface booking_platform in radius results too (keeps API + model in sync).
drop function if exists public.barbershops_within_radius(double precision, double precision, integer);

create function public.barbershops_within_radius(
    lat       double precision,
    lng       double precision,
    radius_m  integer default 2000
)
returns table (
    id               uuid,
    name             text,
    address          text,
    phone            text,
    booking_url      text,
    google_place_id  text,
    lat              double precision,
    lng              double precision,
    opening_hours    jsonb,
    photo_url        text,
    photo_urls       jsonb,
    rating           numeric,
    rating_count     int,
    place_type       text,
    booking_platform text,
    distance_m       double precision
)
language sql
stable
as $$
    select
        b.id, b.name, b.address, b.phone, b.booking_url, b.google_place_id,
        st_y(b.location::geometry) as lat,
        st_x(b.location::geometry) as lng,
        b.opening_hours,
        b.photo_url,
        coalesce(b.photo_urls, '[]'::jsonb),
        b.rating,
        b.rating_count,
        b.place_type,
        b.booking_platform,
        st_distance(b.location, st_setsrid(st_makepoint(lng, lat), 4326)::geography) as distance_m
    from public.barbershops b
    where b.location is not null
      and b.place_type in ('barber_shop', 'hair_care')
      and st_dwithin(
            b.location,
            st_setsrid(st_makepoint(lng, lat), 4326)::geography,
            radius_m
      )
    order by distance_m asc;
$$;
