-- Safe slot sync RPC used by the Scraping Agent.
--
-- Inserts a new slot as 'free'. On conflict (same shop + time + service):
--   - updates price only when the slot is still 'free' (not locked/booked)
--   - leaves locked/booked slots completely untouched
-- This prevents the scraping loop from resetting a slot a user is mid-booking.
create or replace function public.upsert_free_slot(
    p_barbershop_id uuid,
    p_service_name  text,
    p_slot_time     timestamptz,
    p_price         numeric default null
)
returns void
language sql
security definer
set search_path = public
as $$
    insert into public.available_slots
        (barbershop_id, service_name, slot_time, price, status)
    values
        (p_barbershop_id, p_service_name, p_slot_time, p_price, 'free')
    on conflict (barbershop_id, slot_time, service_name)
    do update
        set price = excluded.price
        where public.available_slots.status = 'free';
$$;
