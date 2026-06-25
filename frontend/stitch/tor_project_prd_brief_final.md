# Tor (תור) — Project Requirements Document (PRD)

## 1. Executive Summary
**Tor** (Hebrew: **תּוֹר** — "appointment") is a premium barber-booking aggregator. It bridges the gap between high-end barbershops and clients through a dual-interface ecosystem: a slick consumer discovery app and a robust business management dashboard. The platform's core value is real-time synchronization, eliminating double-bookings and providing integrated no-show protection.

---

## 2. Brand & Design System
The visual identity is "Premium Dark," designed to evoke the moody, high-end atmosphere of a modern barbershop.

### 2.1 Visual Language
- **Theme:** Dark-first aesthetic.
- **Canvas Background:** `#09090B` (Near-black).
- **Primary Accent:** Gold `#EFB200` (Used for "earned" attention: active states, ratings, and primary CTAs).
- **Secondary Surfaces:** Gradated dark greys (`#101012` to `#202023`).
- **Typography:** 
  - **Heebo:** Primary sans-serif for UI text (Hebrew/English).
  - **JetBrains Mono:** Monospaced data for times, prices, and countdowns.
- **Corner Radius:** 20px (Cards), 16px (Buttons/Inputs), Full-pill (Chips/Avatars).

### 2.2 Directionality
- **Primary:** RTL (Hebrew).
- **Secondary:** LTR (English toggle supported).
- **Numbers/Money:** Always LTR (Standard numerals).

---

## 3. Consumer App (A)
Targeted at users looking for a high-quality, frictionless booking experience.

### 3.1 Discovery & Search
- **Geolocation:** Real-time user location mapping with "Available Near You" carousels.
- **Advanced Filtering:** Funnel-based search by service type, budget (slider), date, and rating.
- **Map Mode:** Interactive map with barber pins and transit time estimates (Walking, Car, Bike, Transit).
- **Barber Profile:** Portfolio grids, verified reviews (integrated with Google), and service menus.

### 3.2 Booking & Payments
- **Real-time Sync:** 5-minute "Slot Lock" during checkout to prevent race conditions.
- **Payment Methods:** Apple Pay, Credit Card (Visa/Mastercard).
- **No-Show Protection:** ₪40 charge policy for late cancellations or no-shows.
- **Success State:** High-visibility confirmation with "Add to Calendar" and "Navigate" options.

### 3.3 User Profile
- **My Bookings:** Tracking upcoming cuts with a gold "Glow" countdown.
- **Favorites:** Saved barbers for one-tap rebooking.
- **Account:** Personal details, payment management, and language toggles.

---

## 4. Barber Dashboard (B)
A business suite for shop owners to manage operations on the go.

### 4.1 Calendar Management
- **Daily Roster:** Time-ordered view of appointments, color-coded by status (Completed, Upcoming, Pending, Break).
- **Manual Entry:** Rapid "Add Appointment" form for walk-ins.
- **Staff Filtering:** Toggle view by individual barber or full shop overview.

### 4.2 Staff & Services
- **Staff Roster:** Manage employee profiles (B&W portraits), roles, and active/inactive status.
- **Service Catalog:** Dynamic pricing and duration management that syncs instantly to the consumer app.

### 4.3 Analytics
- **Performance:** Revenue charts, visit counts, and status breakdown donut charts.
- **Time Periods:** Toggle views across 1M, 3M, 6M, 1Y, and All-time.

---

## 5. Technical Specifications
### 5.1 API Architecture
- **Sync Engine:** Webhook-first synchronization with external barbershop software.
- **Locking API:** Atomic POST request for slot reservation with a 5-minute TTL.
- **Payment Gateway:** Secure SSL encryption and direct Apple Pay token processing.

### 5.2 Localization
- **Bilingual Core:** Centralized dictionary for HE/EN content.
- **RTL Transformer:** Middleware to mirror UI elements based on selected locale.

---

## 6. Project Status
- **Design System:** Completed.
- **Consumer App Screens:** Core flow (Home, Profile, Booking, Checkout, Favorites) completed.
- **Barber Dashboard Screens:** Management core (Calendar, Stats, Staff, Services) completed.
- **Onboarding:** Multi-step business setup and client registration flows completed.
