# Tor (תור) — Product Requirements Document (PRD)

## 1. Product Overview
**Tor** is a high-end barber-booking aggregator designed to bridge the gap between premium barbershops and their clients. The platform consists of two primary interfaces:
- **Consumer App:** For users to discover, filter, and book real-time appointments.
- **Barber Dashboard:** A management suite for shop owners to handle scheduling, staff, services, and analytics.

**Core Value Proposition:** Seamless, real-time synchronization between client needs and barber availability with integrated no-show protection and a premium dark-mode aesthetic.

---

## 2. Design System & Visual Identity
The platform follows a "Premium Dark" theme, sampled from established luxury brand patterns.

- **Canvas Background:** `#09090B` (Near-black).
- **Primary Accent:** Gold `#EFB200` (Used for active states, ratings, and primary CTAs).
- **Secondary Surfaces:** Gradated dark greys (`#101012` to `#202023`).
- **Typography:** 
  - **Heebo:** Primary sans-serif for Hebrew and English UI text.
  - **JetBrains Mono:** For monospace data (times, prices, countdowns).
- **Corner Radius:** 20px for cards, 16px for buttons/inputs, full-pill for chips/avatars.
- **Direction:** RTL (Right-to-Left) for Hebrew layout, with LTR support for numerals and English toggle.

---

## 3. Consumer App Features (A)

### A1. Discovery & Search
- **Home Screen:** Features a geolocation header, search bar, and segmented list/map toggle.
- **Filtering:** Advanced funnel-based filtering for budget (slider), date/time, service type, and rating.
- **Map Mode:** Full-screen interactive map with barber pins and transit time estimates (Walking, Car, Bike, Transit).
- **Barber Cards:** High-fidelity cards showing ratings, available slots, and B&W portraits.

### A2. Booking Flow
- **Real-time Sync:** Live calendar integration with real-time slot locking (5-minute hold during checkout).
- **Service Selection:** Tiered service cards (Scissor cut, Beard trim, etc.).
- **Checkout:** Integrated payment support (Apple Pay, Credit Card) with SSL encryption badges.

### A3. User Profile
- **My Bookings:** Tracking upcoming appointments with a gold glow/countdown for the next visit.
- **Favorites:** Quick-access list of saved barbers.
- **Account Management:** Profile photo updates, payment method management, and notification settings.

---

## 4. Barber Dashboard Features (B)

### B1. Calendar Management
- **Daily View:** Time-ordered list of appointments color-coded by status (Completed, Upcoming, Pending, Break).
- **Manual Entry:** Ability for barbers to manually insert walk-in appointments.
- **Staff Filters:** Filter view by individual barber or view the whole shop at once.

### B2. Staff & Service Management
- **Staff Roster:** B&W avatar-based list with active/inactive toggles that sync with the consumer-facing availability.
- **Service Catalog:** Full control over pricing, duration, and descriptions.

### B3. Analytics
- **Performance Tracking:** Revenue charts, visit counts, and status breakdown (donut charts) with 1M to 1Y time-period toggling.

---

## 5. Technical Requirements & Business Logic
- **Localization:** Full Hebrew/English bilingual support.
- **No-Show Protection:** Implementation of a cancellation fee policy (e.g., ₪40 charge for late cancels/no-shows).
- **Integration:** OAuth-based sync with existing barbershop scheduling software and Google Calendar.
- **Notification System:** Multi-channel alerts (SMS, Push, Email) for appointment reminders.

---

## 6. Success Metrics
- **Booking Conversion:** Ratio of profile views to completed bookings.
- **Retention:** Number of "Book Again" actions from the user history.
- **Operational Efficiency:** Reduction in manual entry for shop owners through real-time consumer sync.
