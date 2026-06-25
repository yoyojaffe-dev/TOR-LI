-- Tor-li initial schema: PostGIS, core tables, radius search + pessimistic locking RPCs.

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
create extension if not exists postgis;
create extension if not exists "pgcrypto";  -- gen_random_uuid()

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------
create table if not exists public.barbershops (
    id              uuid primary key default gen_random_uuid(),
    name            text not null,
    address         text,
    phone           text,
    booking_url     text,
    google_place_id text unique,
    location        geography(Point, 4326),
    opening_hours   jsonb,
    created_at      timestamptz not null default now()
);
create index if not exists barbershops_location_gix
    on public.barbershops using gist (location);

do $$ begin
    create type public.slot_status as enum ('free', 'locked', 'booked');
exception when duplicate_object then null;
end $$;

create table if not exists public.available_slots (
    id            uuid primary key default gen_random_uuid(),
    barbershop_id uuid not null references public.barbershops(id) on delete cascade,
    service_name  text not null,
    price         numeric(10, 2),
    slot_time     timestamptz not null,
    status        public.slot_status not null default 'free',
    locked_until  timestamptz,
    locked_by     text,
    created_at    timestamptz not null default now(),
    unique (barbershop_id, slot_time, service_name)
);
create index if not exists available_slots_shop_time_idx
    on public.available_slots (barbershop_id, slot_time);

create table if not exists public.bookings (
    id             uuid primary key default gen_random_uuid(),
    slot_id        uuid not null references public.available_slots(id) on delete cascade,
    customer_name  text not null,
    customer_phone text not null,
    status         text not null default 'confirmed',
    created_at     timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- RPC: barbershops within radius (nearest first)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- RPC: upsert barbershop (sets PostGIS point from lat/lng)
-- ---------------------------------------------------------------------------
create or replace function public.upsert_barbershop(
    p_name text,
    p_lat double precision,
    p_lng double precision,
    p_address text default null,
    p_phone text default null,
    p_booking_url text default null,
    p_google_place_id text default null
)
returns uuid
language plpgsql
as $$
declare
    v_id uuid;
begin
    insert into public.barbershops (name, address, phone, booking_url, google_place_id, location)
    values (
        p_name, p_address, p_phone, p_booking_url, p_google_place_id,
        st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography
    )
    on conflict (google_place_id) do update
        set name = excluded.name,
            address = excluded.address,
            phone = excluded.phone,
            booking_url = excluded.booking_url,
            location = excluded.location
    returning id into v_id;
    return v_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- RPC: pessimistic locking
-- ---------------------------------------------------------------------------
create or replace function public.lock_slot(
    p_slot_id uuid,
    p_user text,
    p_ttl_seconds integer default 90
)
returns table (success boolean, locked_until timestamptz, message text)
language plpgsql
as $$
declare
    v_until timestamptz := now() + make_interval(secs => p_ttl_seconds);
    v_rows integer;
begin
    update public.available_slots s
        set status = 'locked',
            locked_by = p_user,
            locked_until = v_until
    where s.id = p_slot_id
      and (
            s.status = 'free'
            or (s.status = 'locked' and s.locked_until < now())
            or (s.status = 'locked' and s.locked_by = p_user)
      );
    get diagnostics v_rows = row_count;

    if v_rows = 1 then
        return query select true, v_until, 'locked'::text;
    else
        return query select false, null::timestamptz, 'slot already locked or booked'::text;
    end if;
end;
$$;

create or replace function public.release_slot(
    p_slot_id uuid,
    p_user text
)
returns table (success boolean, message text)
language plpgsql
as $$
declare
    v_rows integer;
begin
    update public.available_slots s
        set status = 'free', locked_by = null, locked_until = null
    where s.id = p_slot_id
      and s.status = 'locked'
      and s.locked_by = p_user;
    get diagnostics v_rows = row_count;
    return query select (v_rows = 1), case when v_rows = 1 then 'released' else 'not lock holder' end;
end;
$$;

create or replace function public.confirm_booking(
    p_slot_id uuid,
    p_user text,
    p_booking_id uuid
)
returns table (success boolean, status text, message text)
language plpgsql
as $$
declare
    v_rows integer;
begin
    update public.available_slots s
        set status = 'booked'
    where s.id = p_slot_id
      and s.status = 'locked'
      and s.locked_by = p_user
      and s.locked_until >= now();
    get diagnostics v_rows = row_count;

    if v_rows <> 1 then
        return query select false, 'failed'::text, 'lock expired or not held'::text;
        return;
    end if;
    return query select true, 'booked'::text, 'confirmed'::text;
end;
$$;

-- ---------------------------------------------------------------------------
-- Realtime: push available_slots changes to subscribed clients
-- ---------------------------------------------------------------------------
do $$ begin
    alter publication supabase_realtime add table public.available_slots;
exception when duplicate_object then null;
end $$;
