-- Grant DML on the new tables.
--
-- BUG FIX: MCP-created tables did NOT receive Supabase's default privilege
-- grants, so anon/authenticated/service_role had only REFERENCES,TRIGGER,
-- TRUNCATE — no SELECT/INSERT/UPDATE/DELETE. Every RLS policy on these tables
-- was therefore unreachable (PostgREST returns "permission denied for table"
-- before RLS is evaluated), and even service_role could not write (RLS bypass
-- does NOT bypass table privileges). Grant DML to match policy intent.
-- anon intentionally gets nothing (spec: these tables are authenticated-only).

-- users: own-row select/insert/update
grant select, insert, update         on public.users        to authenticated;
grant select, insert, update, delete on public.users        to service_role;

-- services: read for authenticated, writes gated to owner by RLS
grant select, insert, update, delete on public.services     to authenticated;
grant select, insert, update, delete on public.services     to service_role;

-- staff: same model
grant select, insert, update, delete on public.staff        to authenticated;
grant select, insert, update, delete on public.staff        to service_role;

-- appointments: client select+insert own, owner select; no client update/delete policy
grant select, insert                 on public.appointments to authenticated;
grant select, insert, update, delete on public.appointments to service_role;
