-- Grant owner DML on existing tables.
--
-- BUG FIX: the owner-scoped write policies added on barbershops and
-- available_slots were unreachable because authenticated had SELECT only.
-- Grant the write privileges those policies gate. RLS still restricts every
-- write to the shop owner (owner_id = auth.uid() / is_shop_owner()).
--
-- NOTE: barbershops service_role intentionally keeps SELECT only — the app
-- writes shops via the upsert_barbershop SECURITY DEFINER RPC, not direct DML.

-- barbershops: owner insert/update (spec: no delete)
grant insert, update         on public.barbershops     to authenticated;

-- available_slots: owner insert/update/delete
grant insert, update, delete on public.available_slots to authenticated;
