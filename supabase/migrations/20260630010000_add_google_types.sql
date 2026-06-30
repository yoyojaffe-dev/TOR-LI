-- Store the real Google Places `types` array per shop so legacy rows (inserted
-- before the men's-barbershop classifier existed) can be re-verified, and so the
-- consumer/agent place_type filters have a real signal to trust.
--
-- Backfilled by scripts/run_reclassify.py: it re-fetches each shop's Google
-- `types`, re-runs the existing _is_mens_barbershop classifier, demotes
-- non-barbers to place_type='non_barber', and stamps google_types on every row
-- it processes. NULL therefore means "not yet re-classified" (the resume marker).
alter table public.barbershops add column if not exists google_types jsonb;
