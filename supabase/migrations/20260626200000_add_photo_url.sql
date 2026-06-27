-- Add photo_url to barbershops so discovery agent can store the first
-- Google Places photo. Frontend renders it directly as <img src>.

alter table public.barbershops add column if not exists photo_url text;

-- Extend upsert_barbershop to carry the photo URL (default null so
-- existing callers without the param keep working).
create or replace function public.upsert_barbershop(
    p_name text,
    p_lat double precision,
    p_lng double precision,
    p_address text default null,
    p_phone text default null,
    p_booking_url text default null,
    p_google_place_id text default null,
    p_photo_url text default null
)
returns uuid
language plpgsql
as $$
declare
    v_id uuid;
begin
    insert into public.barbershops (name, address, phone, booking_url, google_place_id, location, photo_url)
    values (
        p_name, p_address, p_phone, p_booking_url, p_google_place_id,
        st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography,
        p_photo_url
    )
    on conflict (google_place_id) do update
        set name         = excluded.name,
            address      = excluded.address,
            phone        = excluded.phone,
            booking_url  = excluded.booking_url,
            location     = excluded.location,
            photo_url    = coalesce(excluded.photo_url, public.barbershops.photo_url)
    returning id into v_id;
    return v_id;
end;
$$;

-- Expose photo_url from the radius search RPC so the frontend gets it.
create or replace function public.barbershops_within_radius(
    lat double precision,
    lng double precision,
    radius_m integer default 2000
)
returns table (
    id uuid,
    name text,
    address text,
    phone text,
    booking_url text,
    google_place_id text,
    lat double precision,
    lng double precision,
    opening_hours jsonb,
    photo_url text,
    distance_m double precision
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
        st_distance(b.location, st_setsrid(st_makepoint(lng, lat), 4326)::geography) as distance_m
    from public.barbershops b
    where b.location is not null
      and st_dwithin(
            b.location,
            st_setsrid(st_makepoint(lng, lat), 4326)::geography,
            radius_m
      )
    order by distance_m asc;
$$;
