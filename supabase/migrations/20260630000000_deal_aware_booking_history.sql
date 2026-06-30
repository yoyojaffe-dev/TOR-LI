-- Make the consumer booking-history price deal-aware.
--
-- bookings have no price column of their own — the price shown in "ההזמנות שלי"
-- comes from this RPC, which previously returned the slot's regular price even
-- for last-minute-deal slots. A booked deal slot must report the deal price
-- (what the customer was actually charged), falling back to the regular price.
--
-- Signature unchanged (price stays a single numeric column); only the price
-- expression changes, so `create or replace` is sufficient. No app/model change
-- is needed — BookingHistoryItem.price already maps to this column.
create or replace function public.bookings_for_user(p_user text)
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
language sql
security definer
set search_path to 'public'
as $$
    select b.id, b.status, b.created_at,
           s.service_name,
           case when s.is_deal and s.deal_price is not null
                then s.deal_price else s.price end as price,
           s.slot_time,
           bs.id, bs.name, bs.address
    from public.bookings b
    join public.available_slots s on s.id = b.slot_id
    join public.barbershops bs on bs.id = s.barbershop_id
    where b.user_token = p_user
    order by s.slot_time desc;
$$;

grant execute on function
    public.bookings_for_user(text)
    to anon, authenticated, service_role;
