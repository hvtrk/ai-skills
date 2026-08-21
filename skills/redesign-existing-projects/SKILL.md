---
name: redesign-existing-projects
description: UI/UX aesthetic audit and visual restyling engine. Audits generic AI design patterns and applies modern typography, color palettes, responsive layouts, and spring animations without rewriting backend logic.
---

# UI/UX Redesign & Visual Polish Playbook

Use this skill when auditing, restyling, or modernizing an existing web application or frontend interface.

## 1. Visual Audit: Eliminate Generic AI Design Fingerprints
- **Typography**: Replace default browser/Inter fonts with expressive type pairings (e.g. Geist, Outfit, Cabinet Grotesk, Satoshi). Ensure tabular numbers (`tabular-nums`) for data tables.
- **Color Palettes**: Replace harsh `#000000` with rich off-blacks (`#0a0a0a`, `#121212`). Use a single considered accent color (saturation < 80%) instead of random multi-colored gradients.
- **Surfaces & Shadows**: Tint shadows to match background hues. Add subtle noise/texture overlays to avoid sterile flat surfaces.

## 2. Layout & Spacing
- **Break Rigid Symmetry**: Use asymmetrical grids, staggered cards, and generous whitespace.
- **Mobile Viewport Fixes**: Use `min-height: 100dvh` instead of `100vh` to avoid mobile browser toolbar jumping.
- **Container Constraints**: Standardize max-widths (1200–1440px) with centered margins.

## 3. Micro-Interactions & Motion
- **Interactive Feedback**: Add smooth hover states, active press scaling (`scale(0.98)`), and focus-visible rings for accessibility.
- **Spring Physics**: Use spring-based transitions for natural, weighty feel.
- **Staggered Reveals**: Cascade list items and card elements into view with slight delays.

## 4. Complete UI State Handling
Every redesigned view must handle all 4 states:
1. **Loading**: Cohesive layout skeletons matching real content shapes.
2. **Empty**: Engaging, helpful empty state views with a primary CTA.
3. **Error**: User-friendly inline error alerts with retry triggers.
4. **Success**: The polished interactive interface.
