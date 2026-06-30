-- Make upsert_service gap-fill price/duration/category on re-enrichment.
--
-- The original RPC was `on conflict ... do nothing` (insert-only), so once a
-- service row existed, a later enrichment pass could never backfill a price that
-- was missing the first time (e.g. when the booking platform wasn't yet trusted
-- by is_pricing_source). With the pricing allowlist widened to calmark/eztor/
-- cut-shave, the 8 shops on those platforms already have null-price rows from the
-- first pass; this lets a re-pass populate them.
--
-- `coalesce(existing, excluded)` only fills when the stored value is NULL, so an
-- owner-entered price/duration/category (not null) is never clobbered by a
-- scraped value — preserving the "never clobber owner rows" invariant.
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
    on conflict (shop_id, lower(name), coalesce(staff_id::text, '')) do update
        set price         = coalesce(public.services.price, excluded.price),
            duration_mins = coalesce(public.services.duration_mins, excluded.duration_mins),
            category      = coalesce(public.services.category, excluded.category)
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
