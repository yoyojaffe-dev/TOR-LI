-- Availability overrides ("blocker" logic): a shop (optionally one staff member)
-- is closed on a date, either all day or for a time window. Times are LOCAL
-- (Asia/Jerusalem). The booking engine cross-references these:
--   * free_slots() / list_slots hide blocked slots from the consumer;
--   * lock_slot() authoritatively rejects a blocked slot at booking time.
-- Applied to the live project via the Supabase MCP; recorded here to keep repo
-- and DB in sync.

create table if not exists public.availability_overrides (
  id            uuid primary key default gen_random_uuid(),
  barbershop_id uuid not null references public.barbershops(id) on delete cascade,
  staff_id      uuid references public.staff(id) on delete cascade,   -- null = whole shop
  date          date not null,
  all_day       boolean not null default true,
  start_time    time,                                                  -- used when all_day=false
  end_time      time,
  note          text,
  created_at    timestamptz not null default now()
);
create index if not exists availability_overrides_shop_date_idx
  on public.availability_overrides (barbershop_id, date);

alter table public.availability_overrides enable row level security;
grant select on public.availability_overrides to anon, authenticated;
grant insert, update, delete on public.availability_overrides to authenticated;
drop policy if exists "overrides read" on public.availability_overrides;
create policy "overrides read" on public.availability_overrides
  for select to anon, authenticated using (true);
drop policy if exists "overrides owner write" on public.availability_overrides;
create policy "overrides owner write" on public.availability_overrides
  for all to authenticated
  using (public.is_shop_owner(barbershop_id))
  with check (public.is_shop_owner(barbershop_id));

-- Does a slot fall inside any override? (local-time aware)
create or replace function public.is_slot_blocked(p_slot_id uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1
    from public.available_slots s
    join public.availability_overrides o on o.barbershop_id = s.barbershop_id
    where s.id = p_slot_id
      and o.date = (s.slot_time at time zone 'Asia/Jerusalem')::date
      and (o.all_day
           or ((s.slot_time at time zone 'Asia/Jerusalem')::time >= o.start_time
               and (s.slot_time at time zone 'Asia/Jerusalem')::time <  o.end_time))
      and (o.staff_id is null or o.staff_id = s.staff_id)
  );
$$;

-- Free, upcoming, non-blocked slots for a shop (consumer read path).
create or replace function public.free_slots(p_barbershop_id uuid)
returns setof public.available_slots language sql stable security definer set search_path = public as $$
  select s.* from public.available_slots s
  where s.barbershop_id = p_barbershop_id and s.status = 'free' and s.slot_time > now()
    and not public.is_slot_blocked(s.id)
  order by s.slot_time;
$$;
grant execute on function public.is_slot_blocked(uuid) to anon, authenticated, service_role;
grant execute on function public.free_slots(uuid) to anon, authenticated, service_role;

-- Authoritative gate: lock_slot rejects a blocked slot (existing body preserved).
create or replace function public.lock_slot(p_slot_id uuid, p_user text, p_ttl_seconds integer default 90)
returns table(success boolean, locked_until timestamptz, message text)
language plpgsql security definer set search_path = public as $function$
declare
  v_until timestamptz := now() + make_interval(secs => p_ttl_seconds);
  v_rows integer;
begin
  if public.is_slot_blocked(p_slot_id) then
    return query select false, null::timestamptz, 'time blocked by the shop'::text;
    return;
  end if;
  update public.available_slots s
     set status = 'locked', locked_by = p_user, locked_until = v_until
   where s.id = p_slot_id
     and (s.status = 'free'
          or (s.status = 'locked' and s.locked_until < now())
          or (s.status = 'locked' and s.locked_by = p_user));
  get diagnostics v_rows = row_count;
  if v_rows = 1 then
    return query select true, v_until, 'locked'::text;
  else
    return query select false, null::timestamptz, 'slot already locked or booked'::text;
  end if;
end;
$function$;
