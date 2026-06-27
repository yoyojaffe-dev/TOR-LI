-- Direct INSERT/UPDATE grant so the opening_hours PATCH in the discovery
-- agent (which calls .table().update() outside the RPC) also succeeds.
grant insert, update on public.barbershops to service_role;
