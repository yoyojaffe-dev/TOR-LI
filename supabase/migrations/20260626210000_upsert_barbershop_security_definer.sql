-- upsert_barbershop was missing SECURITY DEFINER, so calls from the
-- service_role were hitting permission denied on the barbershops table.
-- Adding it makes the function run as its owner (postgres) which has full
-- table access, consistent with all other write RPCs in this project.
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
security definer
set search_path to 'public'
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
        set name        = excluded.name,
            address     = excluded.address,
            phone       = excluded.phone,
            booking_url = excluded.booking_url,
            location    = excluded.location,
            photo_url   = coalesce(excluded.photo_url, public.barbershops.photo_url)
    returning id into v_id;
    return v_id;
end;
$$;

grant execute on function public.upsert_barbershop(text, double precision, double precision, text, text, text, text, text)
    to anon, authenticated, service_role;
