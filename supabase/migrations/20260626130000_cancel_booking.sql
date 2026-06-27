-- Cancel a booking: mark it cancelled and free the slot back up. Scoped to the
-- booking's owner (user_token) so a user can only cancel their own.
create or replace function public.cancel_booking(
    p_booking_id uuid,
    p_user       text
)
returns table(success boolean, message text)
language plpgsql
security definer
set search_path to 'public'
as $$
declare
    v_slot uuid;
begin
    update public.bookings
        set status = 'cancelled'
    where id = p_booking_id
      and user_token = p_user
      and status = 'confirmed'
    returning slot_id into v_slot;

    if v_slot is null then
        return query select false, 'booking not found or already cancelled'::text;
        return;
    end if;

    -- Release the slot so others can book it again.
    update public.available_slots
        set status = 'free', locked_by = null, locked_until = null
    where id = v_slot;

    return query select true, 'cancelled'::text;
end;
$$;

grant execute on function public.cancel_booking(uuid, text)
    to anon, authenticated, service_role;
