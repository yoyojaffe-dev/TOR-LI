-- Persist bookings + scope them to the lock holder, and expose a read RPC.
-- Previously confirm_booking only flipped the slot to 'booked' and never wrote
-- a bookings row, so there was no booking history for the "My Bookings" view.

-- 1. Associate each booking with the browser token that held the lock.
alter table public.bookings add column if not exists user_token text;
create index if not exists bookings_user_token_idx on public.bookings (user_token);

-- 2. confirm_booking now inserts the booking row (with customer details) AND
--    flips the slot, atomically. Drop the old 3-arg version to avoid overload
--    ambiguity.
drop function if exists public.confirm_booking(uuid, text, uuid);

create or replace function public.confirm_booking(
    p_slot_id       uuid,
    p_user          text,
    p_booking_id    uuid,
    p_customer_name  text default null,
    p_customer_phone text default null
)
returns table(success boolean, status text, message text)
language plpgsql
security definer
set search_path to 'public'
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

    insert into public.bookings
        (id, slot_id, customer_name, customer_phone, user_token, status)
    values
        (p_booking_id, p_slot_id, p_customer_name, p_customer_phone, p_user, 'confirmed');

    return query select true, 'booked'::text, 'confirmed'::text;
end;
$$;

-- 3. Read a user's bookings joined with slot + shop detail for the UI.
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
           s.service_name, s.price, s.slot_time,
           bs.id, bs.name, bs.address
    from public.bookings b
    join public.available_slots s on s.id = b.slot_id
    join public.barbershops bs on bs.id = s.barbershop_id
    where b.user_token = p_user
    order by s.slot_time desc;
$$;

grant execute on function
    public.confirm_booking(uuid, text, uuid, text, text)
    to anon, authenticated, service_role;
grant execute on function
    public.bookings_for_user(text)
    to anon, authenticated, service_role;
