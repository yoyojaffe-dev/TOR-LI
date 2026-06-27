-- Harden is_shop_owner: SECURITY INVOKER + restrict EXECUTE.
--
-- The function only reads barbershops (public-readable) and is invoked from RLS
-- policies on services/staff/available_slots/appointments — never from a
-- barbershops policy, so there is no recursion. SECURITY INVOKER avoids the
-- "anon/authenticated can execute SECURITY DEFINER function" advisory.

create or replace function public.is_shop_owner(p_shop_id uuid)
returns boolean
language sql
stable
security invoker
set search_path = public
as $$
  select exists (
    select 1 from public.barbershops b
    where b.id = p_shop_id and b.owner_id = auth.uid()
  );
$$;

-- Not meant as a public RPC; keep available to signed-in users (RLS needs it).
revoke execute on function public.is_shop_owner(uuid) from anon, public;
grant  execute on function public.is_shop_owner(uuid) to authenticated;
