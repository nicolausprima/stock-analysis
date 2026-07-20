# Design System Inspired by Nicolaus Prima

## 1. Visual Theme & Atmosphere

The Nicolaus Prima design system embodies a refined, minimalist aesthetic rooted in contemporary professionalism. The palette centers on warm, earthy neutrals with deliberate restraint, creating an atmosphere of clarity and sophistication. Subtle, nearly imperceptible background patterns and carefully calibrated spacing foster a sense of calm intellectualism. The typography pairing of Epilogue (contemporary sans-serif) with Fraunces (serif accent) establishes hierarchy while maintaining readability. Depth is expressed through soft, restrained shadows rather than bold contrast, encouraging focus on content. This system prioritizes clarity over decoration, making it ideal for portfolios and data-driven applications where user attention must flow naturally from headline to insight.

**Key Characteristics**
- Warm neutral foundation with high-contrast text for accessibility
- Minimalist, content-first layout with generous whitespace
- Soft, nuanced shadows for subtle depth without visual distraction
- Serif-and-sans combination for sophisticated type hierarchy
- Understated interaction states that don't disrupt the visual calm
- Warm beige and off-white surfaces that reduce eye strain

## 2. Color Palette & Roles

### Primary
- **Charcoal Black** (`#1C1C1C`): Primary text, headlines, and high-emphasis content; most frequently used for body copy and primary headings
- **Deep Charcoal** (`#2A2A2A`): Slightly darker variant for interactive elements and strong emphasis where marginally deeper contrast is needed

### Neutral Scale
- **Dark Gray** (`#4A4A4A`): Secondary text, metadata, and supporting content with reduced emphasis
- **Medium Gray** (`#555555`): Tertiary text for de-emphasized labels and helper text
- **Soft Gray** (`#888888`): Disabled states, muted captions, and very light emphasis for background text

### Surface & Borders
- **Cream Surface** (`#F2F0EC`): Primary surface for cards, containers, and content areas; warm off-white with subtle warmth
- **Light Cream** (`#F7F5F2`): Page background and expansive surface areas; the warmest neutral in the palette
- **Border Gray** (`#E8E5E0`): Subtle dividing lines, card borders, and container edges; sits between surface and text for low visual weight

## 3. Typography Rules

### Font Family
- **Primary**: Epilogue (sans-serif) — modern, open letterforms; fallback: `-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif`
- **Accent / Display**: Fraunces (serif) — warm, distinctive letterforms for headings and emphasis; fallback: `Georgia, "Times New Roman", serif`
- **UI/Controls**: Arial (system sans-serif) — for buttons and compact labels where precision is required; fallback: `Helvetica, sans-serif`

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|------|--------|-------------|-----------------|-------|
| Display (H1) | Epilogue | 72px | 500 | 79.2px | 0px | Hero headlines and primary page titles |
| Heading 2 (H2) | Fraunces | 44.8px | 600 | 49.28px | 0px | Section headings, project titles |
| Heading 3 / Link Emphasis | Fraunces | 20px | 600 | 33px | 0px | Card titles, prominent links |
| Body Text | Epilogue | 17.6px | 400 | 28.16px | 0px | Main paragraph content, descriptions |
| List Item | Epilogue | 16px | 400 | 26.4px | 0px | Bulleted and numbered list content |
| Button / Control Text | Arial | 13.33px | 400 | normal | 0px | Primary and secondary button labels |
| Label / Caption | Epilogue | 12.8px | 500 | 21.12px | 0px | Form labels, tag labels, metadata |

### Principles
- Headings use Fraunces at high weights (600) for warmth and distinction; body text relies on Epilogue for clarity and efficiency
- Line heights exceed 1.4× font size to maximize readability on warm backgrounds
- Weights remain conservative (400–600 range) to avoid heaviness; the system avoids extreme weights
- Letter spacing is uniform across the system; ligatures are enabled in all serif contexts
- Button text uses Arial to ensure compact, icon-friendly rendering at small sizes

## 4. Component Stylings

### Buttons

**Primary Button (Large)**
- Background: `#1C1C1C`
- Text Color: `#F7F5F2`
- Padding: `14px 32px`
- Border: `0px none`
- Border Radius: `100px`
- Font: Epilogue, `15.2px`, weight 500, line-height `25.08px`
- Box Shadow: `none`
- Height: `55.08px`
- Hover State: Background darkens to `#0A0A0A`, slight upward offset via transform `translateY(-2px)`
- Active State: Background returns to `#1C1C1C` with pressed visual via `translateY(0px)`

**Secondary Button (Large, Outlined)**
- Background: `transparent`
- Text Color: `#1C1C1C`
- Padding: `14px 32px`
- Border: `1px solid #D8D5D0`
- Border Radius: `100px`
- Font: Epilogue, `15.2px`, weight 500, line-height `25.08px`
- Box Shadow: `none`
- Height: `55.08px`
- Hover State: Background becomes `#F2F0EC`, border remains `#D8D5D0`
- Active State: Background becomes `#E8E5E0`

**Small Pill Button**
- Background: `#F2F0EC`
- Text Color: `#000000`
- Padding: `0px`
- Border: `1px solid #D8D5D0`
- Border Radius: `100px`
- Font: Arial, `13.33px`, weight 400, line-height `normal`
- Box Shadow: `none`
- Width: `52px`
- Height: `28px`
- Hover State: Background becomes `#E8E5E0`

**Icon Button (Circular)**
- Background: `#F2F0EC`
- Text Color: `#1C1C1C`
- Padding: `0px`
- Border: `1px solid #D8D5D0`
- Border Radius: `50%`
- Font: Arial, `13.33px`, weight 400, line-height `normal`
- Box Shadow: `rgba(0, 0, 0, 0.1) 0px 4px 12px 0px`
- Width: `44px`
- Height: `44px`
- Hover State: Box shadow intensifies to `rgba(0, 0, 0, 0.15) 0px 6px 16px 0px`

### Cards & Containers

**Project Card**
- Background: `#F2F0EC`
- Text Color: `#1C1C1C`
- Padding: `32px 28px 24px 28px`
- Border: `1px solid #E8E5E0`
- Border Radius: `8px`
- Font: Epilogue, `16px`, weight 400, line-height `26.4px`
- Box Shadow: `rgba(26, 22, 18, 0.04) 0px 1px 4px 0px, rgba(26, 22, 18, 0.04) 0px 4px 16px 0px`
- Width: `341.33px`
- Height: `367.45px` (min-height, content-responsive)
- Hover State: Box shadow increases to `rgba(26, 22, 18, 0.08) 0px 2px 8px 0px, rgba(26, 22, 18, 0.06) 0px 8px 20px 0px`; slight upward offset via `translateY(-4px)`

**Education / Credential Card**
- Background: `#F2F0EC`
- Text Color: `#1C1C1C`
- Padding: `24px 28px`
- Border: `1px solid #E8E5E0`
- Border Radius: `8px`
- Font: Epilogue, `16px`, weight 400, line-height `26.4px`
- Box Shadow: `rgba(26, 22, 18, 0.04) 0px 1px 4px 0px`
- Display: `flex`, `align-items: center`, `gap: 24px`
- Hover State: Border becomes `#D8D5D0`; background shifts slightly to `#F7F5F2`

### Inputs & Forms

**Text Input**
- Background: `#FFFFFF`
- Text Color: `#1C1C1C`
- Border: `1px solid #E8E5E0`
- Border Radius: `8px`
- Padding: `12px 16px`
- Font: Epilogue, `16px`, weight 400, line-height `26.4px`
- Box Shadow: `none`
- Focus State: Border becomes `#1C1C1C`; box shadow is `rgba(26, 22, 18, 0.04) 0px 0px 0px 3px`

**Form Label**
- Font: Epilogue, `12.8px`, weight 500, line-height `21.12px`
- Text Color: `#4A4A4A`
- Margin Bottom: `8px`

### Navigation

**Header Navigation**
- Background: `transparent`
- Text Color: `#1C1C1C`
- Padding: `0px`
- Font: Epilogue, `16px`, weight 400, line-height `26.4px`
- Border: `none`
- Box Shadow: `none`
- Hover State: Text color becomes `#4A4A4A`
- Active State: Text color remains `#1C1C1C` with bottom border `2px solid #1C1C1C`

**Logo / Wordmark**
- Font: Fraunces, `20px`, weight 600, line-height `33px`
- Text Color: `#1C1C1C`
- Background: `transparent`
- Hover State: Opacity shifts to `0.8`

## 5. Layout Principles

### Spacing System
- **Base Unit**: `4px`
- **Scale**: Multiples of base unit — `4px`, `8px`, `12px`, `16px`, `20px`, `24px`, `28px`, `32px`, `40px`, `64px`, `132px`, `140px`
- **Micro spacing** (`4px–8px`): Component internal gaps, icon margins
- **Small spacing** (`12px–16px`): Section padding, inter-element gaps
- **Medium spacing** (`24px–32px`): Card padding, between-section spacing
- **Large spacing** (`64px–140px`): Page sections, hero margin

### Grid & Container
- **Max Width**: `1200px` (standard container for content)
- **Column Strategy**: 12-column grid at desktop, 6-column at tablet, 1-column at mobile
- **Gutter**: `24px` between columns; `32px` between section blocks
- **Section Pattern**: Hero section spans full width with `140px` padding top/bottom; content sections use `64px` vertical padding with `32px` horizontal gutters

### Whitespace Philosophy
Whitespace is treated as content, not void. Generous margins and padding around text and cards create natural reading zones. No element touches page edges; minimum `32px` padding at all viewport boundaries. Vertical rhythm follows a baseline grid of `4px` increments, ensuring visual harmony across sections.

### Border Radius Scale
- `0px`: No rounding (inputs, standard text)
- `4px`: Subtle rounding for badges and tight components
- `8px`: Cards, containers, moderate visual softness
- `100px`: Buttons and pills for maximum roundness; applied to height and width symmetrically

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| Ground (0) | No shadow | Flat text, backgrounds, and disabled states |
| Raised (1) | `rgba(26, 22, 18, 0.04) 0px 1px 4px 0px, rgba(26, 22, 18, 0.04) 0px 4px 16px 0px` | Cards, content containers, default hover states |
| Floating (2) | `rgba(26, 22, 18, 0.08) 0px 2px 8px 0px, rgba(26, 22, 18, 0.06) 0px 8px 20px 0px` | Cards on hover, expanded modals |
| Interactive (3) | `rgba(0, 0, 0, 0.1) 0px 4px 12px 0px` | Icon buttons, floating action buttons |

**Shadow Philosophy**: Shadows are warm-tinted (`rgba(26, 22, 18, ...)`) rather than neutral black to align with the system's earthy aesthetic. Multiple shadow layers create perceived depth without harsh contrast. Shadows activate on hover to signal interactivity without overwhelming the visual hierarchy. All shadows use `blur-radius` of 4–16px to maintain softness.

## 7. Do's and Don'ts

### Do
- Use `#1C1C1C` for all primary text and headlines; it maintains accessibility on warm surfaces
- Apply Fraunces at `600` weight for H2 headings and project titles; reserve Epilogue for body and navigation
- Maintain minimum `28px` line height for body text to ensure legibility on screens
- Space cards and sections with `32px` minimum gaps; use `64px` for major section breaks
- Implement hover states with shadow elevation and subtle color shifts (`rgba` adjustments)
- Round buttons with `100px` border radius for pill shapes; use `8px` for card corners
- Pair primary buttons (`#1C1C1C`) with secondary outlined buttons for action hierarchies
- Keep borders at `1px` solid `#E8E5E0`; avoid thick strokes

### Don't
- Do not use colors outside the defined neutral and warm palette; maintain design consistency
- Do not stack more than two shadow layers; simplicity is paramount
- Do not apply letter spacing adjustments; the system uses `0px` uniformly
- Do not reduce button padding below `14px` vertical or `32px` horizontal; preserve touch targets
- Do not mix font families within a single heading; choose Fraunces OR Epilogue, not both
- Do not use `#888888` or lighter grays for body text; they fail WCAG AA contrast requirements
- Do not apply animations lasting more than `200ms` for interactions; keep responses immediate
- Do not round corners beyond `8px` except for buttons; over-rounding dilutes the refined aesthetic

## 8. Responsive Behavior

### Breakpoints

| Breakpoint | Width | Key Changes |
|-----------|-------|-------------|
| Mobile | `320px–640px` | Single-column layout, `24px` padding, H1 scales to `48px`, cards stack vertically |
| Tablet | `641px–1024px` | 2–3 column grid, `32px` padding, H1 scales to `56px`, card width adjusts to `calc(50% - 12px)` |
| Desktop | `1025px+` | Full 12-column grid, `64px` max padding, H1 remains `72px`, cards at fixed `341px` width |
| Large Desktop | `1400px+` | Max container `1200px` centered, margins auto-expand |

### Touch Targets
- Minimum interactive element size: `44px` × `44px` (buttons, icon buttons)
- Minimum click/tap area: `48px` × `48px` recommended for mobile
- Minimum link padding: `8px` above/below text for comfortable selection
- Navigation items: `16px` vertical padding, `24px` horizontal padding

### Collapsing Strategy
- **Hero Section**: H1 scales from `72px` (desktop) → `56px` (tablet) → `48px` (mobile); padding reduces from `140px` to `64px` to `32px`
- **Card Grid**: `3 columns` (desktop) → `2 columns` (tablet) → `1 column` (mobile); card width becomes responsive `100%` on mobile with `24px` gutters
- **Navigation**: Inline horizontal menu (desktop/tablet) → hamburger menu toggle (mobile); spacing compresses from `24px` to `16px` gaps
- **Padding & Margins**: Global horizontal padding reduces `32px` → `24px` → `16px` as viewport narrows
- **Typography**: Line heights remain constant; font sizes scale at major breakpoints via rem-based units

## 9. Agent Prompt Guide

### Quick Color Reference
- **Primary Text**: Charcoal Black (`#1C1C1C`)
- **Secondary Text**: Dark Gray (`#4A4A4A`)
- **Tertiary Text**: Soft Gray (`#888888`)
- **Primary Surface**: Cream Surface (`#F2F0EC`)
- **Page Background**: Light Cream (`#F7F5F2`)
- **Borders**: Border Gray (`#E8E5E0`)
- **Primary CTA Button**: Charcoal Black (`#1C1C1C`) background, Cream text (`#F7F5F2`)
- **Secondary CTA Button**: Transparent background, Charcoal text (`#1C1C1C`), `1px solid #D8D5D0` border

### Iteration Guide

1. **Typography Foundation**: Use Epilogue for body, navigation, and general UI; reserve Fraunces exclusively for headings (H2) and display elements. Set all body text to `17.6px` with `28.16px` line height for optimal readability.

2. **Color Hierarchy**: Enforce strict text color usage: `#1C1C1C` for primary text, `#4A4A4A` for secondary, `#888888` for tertiary/disabled. All backgrounds default to `#F2F0EC` (cards) or `#F7F5F2` (page). Never invert this hierarchy.

3. **Spacing Grid**: Every margin, padding, and gap must align to the `4px` base unit. Use `32px` minimum padding for cards/containers, `64px` for section breaks, `24px` for component internal spacing.

4. **Button Design**: All buttons use `100px` border radius (pill shape) except icon buttons which use `50%` (circle). Large buttons: `14px 32px` padding, `55.08px` height, `15.2px` font. Small buttons: `0px` padding, `44px` width/height.

5. **Card Shadows**: Apply dual-layer shadows `rgba(26, 22, 18, 0.04) 0px 1px 4px 0px, rgba(26, 22, 18, 0.04) 0px 4px 16px 0px` to all cards and containers at rest. On hover, elevate to `rgba(26, 22, 18, 0.08) 0px 2px 8px 0px, rgba(26, 22, 18, 0.06) 0px 8px 20px 0px`.

6. **Interactive States**: Hover states activate shadows and subtle color shifts (e.g., `#F2F0EC` → `#E8E5E0`). Avoid color inversion; maintain warm aesthetic. Use `transform: translateY(-2px)` for gentle lift on hover; revert on active.

7. **Responsive Scaling**: H1 scales `72px` (desktop) → `56px` (tablet) → `48px` (mobile). Page padding: `64px` (desktop) → `32px` (mobile). Cards maintain fixed width on desktop, become `100%` width on mobile with `24px` gutters.

8. **Border & Divider**: All card/container borders use `1px solid #E8E5E0`. Avoid multiple border styles; keep borders thin and unobtrusive. Reserve `#D8D5D0` for interactive borders (focused inputs, active nav).

9. **Accessibility Defaults**: Ensure minimum `44px` × `44px` touch targets for all interactive elements. Maintain `#1C1C1C` text on `#F2F0EC`/`#F7F5F2` surfaces for WCAG AA compliance. Never use `#888888` alone for body text; pair with higher contrast elements.

10. **Container Max-Width**: Wrap all content in a `1200px` max-width container centered with `margin: 0 auto`. Maintain `32px` horizontal gutters at all breakpoints; expand padding rather than container at large viewports.