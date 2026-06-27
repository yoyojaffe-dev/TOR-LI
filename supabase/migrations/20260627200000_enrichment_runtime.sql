-- Enrichment runtime: staleness marker, idempotency indexes, and upsert RPCs
-- for staff / services / external_reviews. Writes come from the EnrichmentAgent
-- (staff/services) and DiscoveryAgent (Google reviews), both service-role.

alter table public.barbershops add column if not exists enriched_at timestamptz;

-- Allow unknown price/duration: generic-page services keep them null (not fake 0).
alter table public.services alter column price drop not null;
alter table public.services alter column duration_mins drop default;
alter table public.services alter column duration_mins drop not null;

-- Idempotency: re-running enrichment must not duplicate rows.
create unique index if not exists staff_shop_name_idx
    on public.staff (shop_id, lower(name));

create unique index if not exists services_shop_name_staff_idx
    on public.services (shop_id, lower(name), coalesce(staff_id::text, ''));

-- upsert_staff: insert if new, return existing id on conflict.
create or replace function public.upsert_staff(
    p_shop_id uuid,
    p_name    text
)
returns uuid
language plpgsql
security definer
set search_path to 'public'
as $$
declare
    v_id uuid;
begin
    insert into public.staff (shop_id, name)
    values (p_shop_id, p_name)
    on conflict (shop_id, lower(name)) do nothing
    returning id into v_id;

    if v_id is null then
        select id into v_id from public.staff
        where shop_id = p_shop_id and lower(name) = lower(p_name)
        limit 1;
    end if;
    return v_id;
end;
$$;

grant execute on function public.upsert_staff(uuid, text) to service_role;

-- upsert_service: insert-if-not-exists (dedup by shop + name + staff). Null
-- price/duration mean "unknown" (kept for generic pages by the agent).
create or replace function public.upsert_service(
    p_shop_id       uuid,
    p_name          text,
    p_category      text default null,
    p_price         integer default null,
    p_duration_mins integer default null,
    p_staff_id      uuid default null
)
returns uuid
language plpgsql
security definer
set search_path to 'public'
as $$
declare
    v_id uuid;
begin
    insert into public.services (shop_id, name, category, price, duration_mins, staff_id)
    values (p_shop_id, p_name, p_category, p_price, p_duration_mins, p_staff_id)
    on conflict (shop_id, lower(name), coalesce(staff_id::text, '')) do nothing
    returning id into v_id;

    if v_id is null then
        select id into v_id from public.services
        where shop_id = p_shop_id
          and lower(name) = lower(p_name)
          and coalesce(staff_id::text, '') = coalesce(p_staff_id::text, '')
        limit 1;
    end if;
    return v_id;
end;
$$;

grant execute on function public.upsert_service(uuid, text, text, integer, integer, uuid) to service_role;

-- upsert_external_review: insert, dedup via the expression unique index.
create or replace function public.upsert_external_review(
    p_barbershop_id uuid,
    p_author        text default null,
    p_rating        numeric default null,
    p_text          text default null,
    p_source        text default 'google',
    p_reviewed_at   timestamptz default null
)
returns void
language plpgsql
security definer
set search_path to 'public'
as $$
begin
    insert into public.external_reviews (barbershop_id, author, rating, text, source, reviewed_at)
    values (p_barbershop_id, p_author, p_rating, p_text, p_source, p_reviewed_at)
    on conflict (barbershop_id, source, md5(coalesce(author, '') || '|' || coalesce(text, '')))
    do nothing;
end;
$$;

grant execute on function public.upsert_external_review(uuid, text, numeric, text, text, timestamptz)
    to service_role;
