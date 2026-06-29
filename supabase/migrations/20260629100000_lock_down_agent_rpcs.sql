-- SECURITY (Critical, audit C1).
-- The agent upsert_* functions are SECURITY DEFINER (they bypass RLS) and were
-- unintentionally executable by `anon`/`authenticated` via PostgreSQL's default
-- PUBLIC EXECUTE grant. That let anyone holding the public anon key write to ANY
-- shop's services/staff/slots/reviews/barbershops through /rest/v1/rpc/upsert_*,
-- defeating the owner-RLS model entirely.
--
-- Revoke EXECUTE from anon/authenticated/public on every overload; only
-- `service_role` (the background agents) may call them. The consumer booking
-- RPCs (lock_slot / confirm_booking / release_slot / free_slots / is_slot_blocked
-- / bookings_for_user / cancel_booking / submit_review / reviews_for_barbershop)
-- intentionally stay anon-callable — they self-enforce via the lock token /
-- definer logic and are NOT touched here.
do $$
declare r record;
begin
  for r in
    select p.oid::regprocedure as sig
    from pg_proc p
    where p.pronamespace = 'public'::regnamespace
      and p.proname in ('upsert_barbershop', 'upsert_service', 'upsert_staff',
                        'upsert_free_slot', 'upsert_external_review', 'rls_auto_enable')
  loop
    execute format('revoke execute on function %s from anon, authenticated, public', r.sig);
  end loop;
end $$;

-- Some overloads relied on the default PUBLIC grant (never had an explicit
-- service_role grant). After revoking PUBLIC above, grant EXECUTE back to
-- service_role explicitly so the background agents keep working.
do $$
declare r record;
begin
  for r in
    select p.oid::regprocedure as sig
    from pg_proc p
    where p.pronamespace = 'public'::regnamespace
      and p.proname in ('upsert_barbershop', 'upsert_service', 'upsert_staff',
                        'upsert_free_slot', 'upsert_external_review', 'rls_auto_enable')
  loop
    execute format('grant execute on function %s to service_role', r.sig);
  end loop;
end $$;
