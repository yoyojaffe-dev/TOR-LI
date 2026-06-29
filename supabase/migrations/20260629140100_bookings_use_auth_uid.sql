-- AUTH: move the consumer booking/review RPCs from an opaque `p_user` token to
-- the authenticated identity `auth.uid()`.
--
-- Previously the consumer passed a random browser token (user_token) that every
-- RPC trusted verbatim as `p_user` — no verification, so anyone could act as
-- anyone. With phone-OTP login the consumer now sends a real GoTrue JWT; these
-- functions read `auth.uid()` (populated by PostgREST from the JWT, even inside
-- SECURITY DEFINER) instead of accepting an identity argument.
--
-- The `user_token` columns on public.bookings / public.reviews are kept as-is
-- (text) and now store `auth.uid()::text`; existing rows keyed by old anonymous
-- tokens are simply orphaned (acceptable — they were never recoverable anyway).
--
-- EXECUTE is revoked from anon and granted to `authenticated` so only logged-in
-- clients can lock/confirm/cancel/review. Read paths that stay anonymous
-- (free_slots, reviews_for_barbershop, available_slots_nearby, active_deals) are
-- untouched. RETURNS TABLE shapes are unchanged so the Pydantic models still fit.
--
-- Applied to the live project (ekugfzrmitvoiamevtfa) via the Supabase MCP;
-- recorded here to keep repo and DB in sync.

-- Drop the old token-arg overloads so only the auth.uid() versions remain.
drop function if exists public.lock_slot(uuid, text, integer);
drop function if exists public.release_slot(uuid, text);
drop function if exists public.confirm_booking(uuid, text, uuid, text, text);
drop function if exists public.cancel_booking(uuid, text);
drop function if exists public.bookings_for_user(text);
drop function if exists public.submit_review(uuid, text, int, text);

-- 1. lock_slot — pessimistic lock for the authenticated caller.
create or replace function public.lock_slot(p_slot_id uuid, p_ttl_seconds integer default 90)
returns table(success boolean, locked_until timestamptz, message text)
language plpgsql security definer set search_path = public as $function$
declare
  v_user  text := auth.uid()::text;
  v_until timestamptz := now() + make_interval(secs => p_ttl_seconds);
  v_rows  integer;
begin
  if v_user is null then
    return query select false, null::timestamptz, 'authentication required'::text;
    return;
  end if;
  if public.is_slot_blocked(p_slot_id) then
    return query select false, null::timestamptz, 'time blocked by the shop'::text;
    return;
  end if;
  update public.available_slots s
     set status = 'locked', locked_by = v_user, locked_until = v_until
   where s.id = p_slot_id
     and (s.status = 'free'
          or (s.status = 'locked' and s.locked_until < now())
          or (s.status = 'locked' and s.locked_by = v_user));
  get diagnostics v_rows = row_count;
  if v_rows = 1 then
    return query select true, v_until, 'locked'::text;
  else
    return query select false, null::timestamptz, 'slot already locked or booked'::text;
  end if;
end;
$function$;

-- 2. release_slot — release a lock the caller holds.
create or replace function public.release_slot(p_slot_id uuid)
returns table(success boolean, message text)
language plpgsql security definer set search_path = public as $$
declare
  v_user text := auth.uid()::text;
  v_rows integer;
begin
  if v_user is null then
    return query select false, 'authentication required'::text;
    return;
  end if;
  update public.available_slots s
     set status = 'free', locked_by = null, locked_until = null
   where s.id = p_slot_id
     and s.status = 'locked'
     and s.locked_by = v_user;
  get diagnostics v_rows = row_count;
  return query select (v_rows = 1),
    case when v_rows = 1 then 'released' else 'not lock holder' end;
end;
$$;

-- 3. confirm_booking — finalise the caller's locked slot into a booking row.
create or replace function public.confirm_booking(
    p_slot_id        uuid,
    p_booking_id     uuid,
    p_customer_name  text default null,
    p_customer_phone text default null
)
returns table(success boolean, status text, message text)
language plpgsql security definer set search_path to 'public' as $$
declare
    v_user text := auth.uid()::text;
    v_rows integer;
begin
    if v_user is null then
        return query select false, 'failed'::text, 'authentication required'::text;
        return;
    end if;
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
        (id, slot_id, customer_name, customer_phone, user_token, status)
    values
        (p_booking_id, p_slot_id, p_customer_name, p_customer_phone, v_user, 'confirmed');

    return query select true, 'booked'::text, 'confirmed'::text;
end;
$$;

-- 4. cancel_booking — cancel the caller's booking and free the slot.
create or replace function public.cancel_booking(p_booking_id uuid)
returns table(success boolean, message text)
language plpgsql security definer set search_path to 'public' as $$
declare
    v_user text := auth.uid()::text;
    v_slot uuid;
begin
    if v_user is null then
        return query select false, 'authentication required'::text;
        return;
    end if;
    update public.bookings
        set status = 'cancelled'
    where id = p_booking_id
      and user_token = v_user
      and status = 'confirmed'
    returning slot_id into v_slot;

    if v_slot is null then
        return query select false, 'booking not found or already cancelled'::text;
        return;
    end if;

    update public.available_slots
        set status = 'free', locked_by = null, locked_until = null
    where id = v_slot;

    return query select true, 'cancelled'::text;
end;
$$;

-- 5. bookings_for_user — the caller's bookings joined with slot + shop detail.
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
           s.service_name, s.price, s.slot_time,
           bs.id, bs.name, bs.address
    from public.bookings b
    join public.available_slots s on s.id = b.slot_id
    join public.barbershops bs on bs.id = s.barbershop_id
    where b.user_token = v_user
    order by s.slot_time desc;
end;
$$;

-- 6. submit_review — review for the caller's completed booking.
create or replace function public.submit_review(
    p_booking_id uuid,
    p_rating     int,
    p_comment    text default null
)
returns table(success boolean, message text)
language plpgsql security definer set search_path to 'public' as $$
declare
    v_user text := auth.uid()::text;
    v_shop uuid;
begin
    if v_user is null then
        return query select false, 'authentication required'::text;
        return;
    end if;
    select bs.id into v_shop
    from public.bookings b
    join public.available_slots s on s.id = b.slot_id
    join public.barbershops bs on bs.id = s.barbershop_id
    where b.id = p_booking_id and b.user_token = v_user;

    if v_shop is null then
        return query select false, 'booking not found for this user'::text;
        return;
    end if;
    if p_rating < 1 or p_rating > 5 then
        return query select false, 'rating must be 1-5'::text;
        return;
    end if;

    insert into public.reviews (booking_id, barbershop_id, user_token, rating, comment)
    values (p_booking_id, v_shop, v_user, p_rating, p_comment)
    on conflict (booking_id) do update
        set rating = excluded.rating, comment = excluded.comment, created_at = now();

    return query select true, 'saved'::text;
end;
$$;

-- Grants: authenticated callers only (anon can no longer book/review).
revoke execute on function public.lock_slot(uuid, integer) from anon, public;
revoke execute on function public.release_slot(uuid) from anon, public;
revoke execute on function public.confirm_booking(uuid, uuid, text, text) from anon, public;
revoke execute on function public.cancel_booking(uuid) from anon, public;
revoke execute on function public.bookings_for_user() from anon, public;
revoke execute on function public.submit_review(uuid, int, text) from anon, public;

grant execute on function public.lock_slot(uuid, integer) to authenticated;
grant execute on function public.release_slot(uuid) to authenticated;
grant execute on function public.confirm_booking(uuid, uuid, text, text) to authenticated;
grant execute on function public.cancel_booking(uuid) to authenticated;
grant execute on function public.bookings_for_user() to authenticated;
grant execute on function public.submit_review(uuid, int, text) to authenticated;
