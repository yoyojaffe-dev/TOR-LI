-- AUTH: auto-provision a public.users profile row for every auth.users account.
--
-- public.users is the "profiles" table (role client|barber|owner, PK = auth.users.id).
-- Previously a profile row was created only by the dev-only /admin/barber-signup
-- path (role='owner'). With phone-OTP client login, GoTrue creates an auth.users
-- row on first verify and we need a matching profile so RLS / joins have a role.
--
-- A SECURITY DEFINER trigger inserts the profile as role='client' on every new
-- auth user. It is idempotent (ON CONFLICT DO NOTHING) so the barber path's
-- subsequent upsert to role='owner' still wins, and re-runs are safe. The phone
-- is copied from auth.users when present (OTP signups carry it).
--
-- Applied to the live project (ekugfzrmitvoiamevtfa) via the Supabase MCP;
-- recorded here to keep repo and DB in sync.

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.users (id, role, phone)
  values (new.id, 'client', new.phone)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Backfill: any existing auth.users without a profile gets a client profile.
-- (Existing owners already have role='owner' rows, so ON CONFLICT skips them.)
insert into public.users (id, role, phone)
select u.id, 'client', u.phone
from auth.users u
on conflict (id) do nothing;
