-- Record the deal-aware slot columns that were previously applied to the live
-- DB out-of-band (referenced by the bookings_for_user RPC in
-- 20260630000000_deal_aware_booking_history.sql) but never captured in a
-- migration. Idempotent so re-applying against the live project is safe.
ALTER TABLE available_slots
  ADD COLUMN IF NOT EXISTS is_deal boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS deal_price numeric;
