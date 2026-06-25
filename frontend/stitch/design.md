---
name: Tor (תור)
colors:
  surface: '#131315'
  surface-dim: '#131315'
  surface-bright: '#39393b'
  surface-container-lowest: '#0e0e10'
  surface-container-low: '#1c1b1d'
  surface-container: '#201f22'
  surface-container-high: '#2a2a2c'
  surface-container-highest: '#353437'
  on-surface: '#e5e1e4'
  on-surface-variant: '#d4c5ac'
  inverse-surface: '#e5e1e4'
  inverse-on-surface: '#313032'
  outline: '#9c8f79'
  outline-variant: '#504533'
  surface-tint: '#fbbc18'
  primary: '#ffd174'
  on-primary: '#402d00'
  primary-container: '#efb200'
  on-primary-container: '#624700'
  inverse-primary: '#7a5900'
  secondary: '#c6c6c7'
  on-secondary: '#2f3131'
  secondary-container: '#454747'
  on-secondary-container: '#b4b5b5'
  tertiary: '#abdeff'
  on-tertiary: '#00344a'
  tertiary-container: '#57c7ff'
  on-tertiary-container: '#005170'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdea1'
  primary-fixed-dim: '#fbbc18'
  on-primary-fixed: '#261900'
  on-primary-fixed-variant: '#5c4300'
  secondary-fixed: '#e2e2e2'
  secondary-fixed-dim: '#c6c6c7'
  on-secondary-fixed: '#1a1c1c'
  on-secondary-fixed-variant: '#454747'
  tertiary-fixed: '#c4e7ff'
  tertiary-fixed-dim: '#7cd0ff'
  on-tertiary-fixed: '#001e2c'
  on-tertiary-fixed-variant: '#004c69'
  background: '#131315'
  on-background: '#e5e1e4'
  surface-variant: '#353437'
  surface-1: '#101012'
  surface-2: '#131214'
  surface-3: '#18171A'
  surface-4: '#202023'
  text-primary: '#FAFAF9'
  text-secondary: '#A1A1AA'
  text-muted: '#71717A'
  success: '#34C759'
  danger: '#FF453A'
  info: '#0A84FF'
  border-light: rgba(255, 255, 255, 0.08)
  gold-glow: rgba(239, 178, 0, 0.15)
typography:
  display-lg:
    fontFamily: Heebo
    fontSize: 40px
    fontWeight: '900'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Heebo
    fontSize: 32px
    fontWeight: '800'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Heebo
    fontSize: 24px
    fontWeight: '800'
    lineHeight: '1.2'
  headline-sm:
    fontFamily: Heebo
    fontSize: 20px
    fontWeight: '700'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Heebo
    fontSize: 18px
    fontWeight: '500'
    lineHeight: '1.5'
  body-md:
    fontFamily: Heebo
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1'
    letterSpacing: 0.05em
  price-lg:
    fontFamily: JetBrains Mono
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1'
  headline-lg-mobile:
    fontFamily: Heebo
    fontSize: 28px
    fontWeight: '800'
    lineHeight: '1.2'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  gutter: 20px
  section-gap: 32px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 24px
---

## Brand & Style
The design system for this barber-booking aggregator is defined by a **Modern, Sleek, and Premium** personality. It is a "dark-first" system that evokes the moody, high-end atmosphere of a contemporary urban barbershop. The brand acts as a digital concierge—direct, efficient, and sophisticated.

The visual style is a blend of **Minimalism** and **Corporate Modern**, utilizing heavy whitespace (within a dark canvas), high-quality photography, and a single, hard-earned accent color to guide the user. 

### Key Visual Principles:
- **Dark-First:** The UI prioritizes a near-black canvas to allow imagery and gold accents to pop.
- **Gold is Earned:** The gold accent is reserved for the most critical actions, active states, and premium "next-up" indicators.
- **RTL-Optimized:** Designed primarily for Hebrew, ensuring the layout flow and alignment feel native and balanced.
- **Tactile Feedback:** Though minimal in appearance, the UI feels physical through subtle tonal layering and scale-based press states.

## Colors
The palette is centered on a deep, near-black neutral base with a single chromatic gold accent. Depth is achieved through a "step-up" surface model rather than shadows alone.

- **Primary (Gold):** Used for primary CTAs, active navigation tabs, prices, and high-value indicators like ratings.
- **Secondary (White):** Reserved for the highest-emphasis functional buttons (e.g., "Pay" or "Navigate") to provide maximum contrast against the dark background.
- **Neutral (Canvas):** A deep `#09090B` serves as the foundation.
- **Surface Tiers:** UI depth is created by incrementally lightening the surface color for cards and containers (`surface-1` through `surface-4`).
- **Semantic Colors:** Green, Red, and Blue are used strictly for status (Success, No-Show/Cancel, and Information).

## Typography
The system uses a dual-font approach to balance editorial style with technical precision.

- **Heebo:** The primary typeface for all Hebrew and Latin text. Headings should be heavy (800-900) and tightly tracked to create a "blocky," premium feel. Body text uses weights 400-500 for legibility.
- **JetBrains Mono:** Used exclusively for "data" elements—prices, times, countdowns, and IDs. The monospaced nature ensures tabular alignment in grids and lists, reinforcing the app's utility.
- **RTL Considerations:** Hebrew text should never be justified; use right-alignment. Casing is applied only to English strings (Sentence case).

## Layout & Spacing
This design system utilizes a **Fixed Grid** philosophy for mobile, optimized for a 430px width (iPhone-class) with a generous 20px outer margin.

- **Grid:** A 4px base unit governs all spatial decisions.
- **Rhythm:** Sections are separated by 32px vertical gaps. Internal card content uses 16px padding.
- **Mobile Adaptive:** On mobile, content is primarily single-column with horizontal carousels for discovery categories (barbers, time slots). 
- **Navigation:** A fixed bottom navigation bar (80px height) with a glassmorphism effect remains persistent across primary views.

## Elevation & Depth
Hierarchy is established through **Tonal Layers** and **Subtle Glassmorphism** rather than traditional heavy shadows.

- **Surface Steps:** Elements "lift" off the canvas by changing fill color (e.g., a card is `#131214` on a `#09090B` background).
- **Hairline Borders:** Use 1px borders with low-opacity white (`rgba(255,255,255,0.08)`) to define edges without adding visual weight.
- **The "Next-Up" Glow:** To signify the most immediate appointment or active state, apply a gold hairline ring and a soft, diffused gold outer glow (`drop-shadow`).
- **Backdrop Blur:** Bottom navigation bars and sticky action containers must use a `backdrop-filter: blur(20px)` with a semi-transparent surface fill to maintain context of the content scrolling beneath.

## Shapes
The shape language is "Soft-Organic," utilizing large radii to offset the "cold" feeling of a dark, technical UI.

- **Cards:** 20px corner radius.
- **Buttons & Inputs:** 16px corner radius.
- **Avatars & Chips:** Always full-pill (rounded-full) to provide a distinct contrast against rectangular content blocks.
- **Interaction:** On press, elements should scale slightly (0.97) with a quick 120ms spring transition.

## Components
Consistent component execution is vital for the premium feel of the design system.

- **Buttons:**
  - *Primary (High Emphasis):* Solid White with black text.
  - *Secondary (Brand):* Solid Gold with black text.
  - *Tertiary (Ghost):* Transparent with a gold or white hairline border.
- **Cards:** Use `surface-1` or `surface-2` fills. Barber cards include a bottom-to-top black gradient overlay on images to ensure text legibility.
- **Chips:** Full-pill shape. Active chips are solid Gold; inactive chips are `surface-3` with muted text.
- **Input Fields:** 16px radius, `surface-1` fill, with `border-light` hairline.
- **Next-Up Card:** This specific component features a 1px gold border and a `gold-glow` drop shadow.
- **Avatars:** Barber portraits are always Black & White circles. User avatars can be color.
- **Navigation:** Bottom nav icons use Lucide (2px stroke). The active state is indicated by a Gold icon and Gold label.