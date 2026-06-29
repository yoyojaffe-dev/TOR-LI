-- Persist the price the customer actually pays on each booking.
--
-- Before this, `bookings` stored no price at all — the "My Bookings" view
-- derived it by joining `available_slots.price`, which is the slot's LIST price.
-- For a last-minute deal (`is_deal` + `deal_price`) that over-reported the cost:
-- the consumer is charged `deal_price`, but history showed the original.
--
-- Fix: snapshot the effective (deal-aware) price onto the booking row at confirm
-- time. The price is derived SERVER-SIDE from the slot being confirmed, never
-- supplied by the client, so it can't be spoofed. The RPC signature is unchanged
-- (still slot_id, booking_id, name, phone) so the Python wrapper / API / frontend
-- need no changes.
--
-- Applied to the live project (ekugfzrmitvoiamevtfa) via the Supabase MCP;
-- recorded here to keep repo and DB in sync.

-- 1. Column to hold the charged amount (nullable: legacy rows stay null and fall
--    back to the slot price in bookings_for_user).
alter table public.bookings add column if not exists price numeric;

-- 2. confirm_booking — snapshot the effective price from the slot, then book.
create or replace function public.confirm_booking(
    p_slot_id        uuid,
    p_booking_id     uuid,
    p_customer_name  text default null,
    p_customer_phone text default null
)
returns table(success boolean, status text, message text)
language plpgsql security definer set search_path to 'public' as $$
declare
    v_user  text := auth.uid()::text;
    v_rows  integer;
    v_price numeric;
begin
    if v_user is null then
        return query select false, 'failed'::text, 'authentication required'::text;
        return;
    end if;

    -- Effective price: the discounted deal_price when this slot is on offer,
    -- otherwise the regular list price. Read before flipping the slot.
    select case when s.is_deal and s.deal_price is not null then s.deal_price else s.price end
      into v_price
      from public.available_slots s
     where s.id = p_slot_id;

    update public.available_slots s
        set status = 'booked'
    where s.id = p_slot_id
      and s.status = 'locked'
      and s.locked_by = v_user
      and s.locked_until >= now();
    get diagnostics v_rows = row_count;

    if v_rows <> 1 then
        return query select false, 'failed'::text, 'lock expired or not held'::text;
        return;
    end if;

    insert into public.bookings
        (id, slot_id, customer_name, customer_phone, user_token, status, price)
    values
        (p_booking_id, p_slot_id, p_customer_name, p_customer_phone, v_user, 'confirmed', v_price);

    return query select true, 'booked'::text, 'confirmed'::text;
end;
$$;

-- 3. bookings_for_user — return the snapshotted price (fall back to the slot's
--    current price for pre-existing rows booked before this column existed).
create or replace function public.bookings_for_user()
returns table(
    booking_id    uuid,
    status        text,
    created_at    timestamptz,
    service_name  text,
    price         numeric,
    slot_time     timestamptz,
    barbershop_id uuid,
    shop_name     text,
    shop_address  text
)
language plpgsql security definer set search_path to 'public' as $$
declare
    v_user text := auth.uid()::text;
begin
    return query
    select b.id, b.status, b.created_at,
           s.service_name, coalesce(b.price, s.price) as price, s.slot_time,
           bs.id, bs.name, bs.address
    from public.bookings b
    join public.available_slots s on s.id = b.slot_id
    join public.barbershops bs on bs.id = s.barbershop_id
    where b.user_token = v_user
    order by s.slot_time desc;
end;
$$;

-- Grants are unchanged (same signatures); CREATE OR REPLACE preserves them.
