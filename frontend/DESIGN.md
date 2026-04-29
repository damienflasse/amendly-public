# DESIGN.md: Visual Identity & Interface Guidelines

## 1. Overview & Creative North Star: "The Editorial Ledger"
The creative direction for this design system is **The Editorial Ledger**. In the high-stakes world of European policy-making, clarity is authority. We move beyond the "generic SaaS" look by treating digital interfaces like premium, high-density editorial documents.

Unlike standard apps that rely on heavy borders and loud buttons, "The Editorial Ledger" uses **Tonal Architecture**. We create hierarchy through intentional asymmetry, overlapping "paper" layers, and a rigorous typographic scale. The goal is a "Quietly Confident" experience that feels as reliable as a legal brief but as fluid as a modern collaborative tool.

---

## 2. Color Tokens & Tonal Architecture
We employ a "No-Line" philosophy. Structure is defined by background shifts and elevation, never by 1px solid strokes.

### Core Palette (unified — Gemini Canvas brand)
| Token | Hex | Role |
| :--- | :--- | :--- |
| `amendly-blue` | `#2563EB` | **Brand primary** — all action buttons, CTAs, interactive focus rings. |
| `amendly-dark` | `#0F172A` | Deep Navy — strong headings, logo, maximum contrast text. |
| `amendly-gray` | `#94A3B8` | Cool Slate — diffs, secondary text, subtle borders. |
| `amendly-light` | `#F8FAFC` | Ghost White — hover backgrounds, page bases. |
| `secondary` | `#0053dc` | Functional accent for inline links and secondary interactive elements. |
| `surface` | `#f7f9fb` | The base "paper" layer. |
| `surface-container-low` | `#f0f4f7` | Secondary regions or sidebar backgrounds. |
| `surface-container-highest`| `#d9e4ea` | Deepest contrast for inset elements or inactive states. |
| `on-surface` | `#2a3439` | High-contrast body text for maximum legibility. |

> **Deprecated:** `primary: #515f74` (Deep Slate) has been removed. All call-to-action elements that previously used `bg-primary` now use `bg-amendly-blue text-white`.

### The "No-Line" Rule
**Explicit Instruction:** Prohibit 1px solid borders for sectioning. 
*   **Do:** Separate a sidebar from a main feed by shifting from `surface` to `surface-container-low`.
*   **Do:** Use a `surface-container-lowest` (#ffffff) card sitting on a `surface` background to create a "lifted" effect.
*   **Don't:** Use `#ddd` or `#eee` lines to box in content.

### Signature Textures & Glassmorphism
For floating menus (modals, dropdowns), use a **Glassmorphism** effect:
*   **Fill:** `surface-container-lowest` at 85% opacity.
*   **Backdrop Blur:** 12px.
*   **Purpose:** To make the UI feel integrated and airy, rather than "pasted on."

---

## 3. Typography: The Policy Scale
We pair **Manrope** (Display/Headlines) for a modern, geometric authority with **Inter** (Body/UI) for world-class legibility across European languages.

| Category | Token | Font | Size | Tracking |
| :--- | :--- | :--- | :--- | :--- |
| **Display** | `display-md` | Manrope | 2.75rem | -0.02em |
| **Headline** | `headline-sm` | Manrope | 1.5rem | -0.01em |
| **Title** | `title-sm` | Inter | 1.0rem | 0 |
| **Body** | `body-md` | Inter | 0.875rem | 0 |
| **Label** | `label-sm` | Inter | 0.6875rem | +0.02em |

**Editorial Intent:** Use `display-md` sparingly for dashboard "At a Glance" stats. Use `headline-sm` for document titles. The tight tracking on Manrope provides a custom, premium feel typical of high-end editorial layouts.

---

## 4. Elevation & Depth: Layering Principle
Instead of traditional drop shadows, we use **Tonal Layering** to define the Z-axis.

1.  **Level 0 (Base):** `surface`
2.  **Level 1 (Sections):** `surface-container-low` (Nested inside Level 0)
3.  **Level 2 (Cards):** `surface-container-lowest` (Sits on Level 0 or 1)

### Ambient Shadows
When an element must float (e.g., a dragged amendment), use an **Ambient Shadow**:
*   **Shadow:** `0px 12px 32px rgba(42, 52, 57, 0.06)`
*   **Ghost Border:** If contrast is low, use `outline-variant` at 15% opacity. Never use a 100% opaque border.

---

## 5. Component Patterns

### The Word-Level Diff System
The core of the tool. Precision is paramount.
*   **Addition:** Background `secondary-container` (#dbe1ff), Text `on-secondary-fixed` (#003798), **Bold**.
*   **Deletion:** Text `outline` (#717c82), Strikethrough, No background.
*   **Container:** Wrap diffs in a `surface-container-lowest` card with `md` (0.375rem) corner radius.

### Status Badges (Semantic)
Badges must use the "Soft Fill" approach:
*   **Accepted:** Background `tertiary-fixed` (#dcddfe), Text `on-tertiary-fixed` (#393c55).
*   **Pending:** Background `primary-fixed` (#d5e3fd), Text `on-primary-fixed` (#324054).
*   **Rejected:** Background `error-container` (#fe8983) at 40% opacity, Text `on-error-container` (#752121).

### Buttons
*   **Primary:** `amendly-blue` background, `white` text. No shadow.
*   **Secondary:** `surface-container-highest` background, `on-surface` text.
*   **Tertiary (Ghost):** No background, `secondary` text.

### Data-Dense Cards
*   **Rule:** Forbid divider lines.
*   **Spacing:** Use the `8` (1.75rem) spacing token for internal padding to allow the text to breathe. Use `body-sm` for metadata (date, author) to maintain a clean hierarchy.

---

## 6. Do's and Don'ts

### Do
*   **Use Asymmetry:** Align document titles to the far left and metadata to the far right to create expansive, premium layouts.
*   **Leverage Whitespace:** Use the `12` (2.75rem) spacing token between major content blocks.
*   **Embrace Tonal Shifts:** Use `surface-dim` for inactive or "archived" amendment states.

### Don't
*   **Don't use pure black:** Use `on-surface` (#2a3439) for text to keep the "Editorial" feel soft and readable.
*   **Don't box everything:** Let content flow. Use the background color of the page to define the boundaries of your work area.
*   **Don't use standard shadows:** If a shadow looks like a "shadow," it's too dark. It should feel like a subtle glow of light.

---

## 7. Spacing Scale (4px/8px Based)
| Token | Value | Use Case |
| :--- | :--- | :--- |
| `1` | 0.2rem | Smallest detail spacing (icon to text). |
| `2` | 0.4rem | Standard component internal gap. |
| `4` | 0.9rem | Tight padding for small cards. |
| `8` | 1.75rem | Standard page margins and section gaps. |
| `12` | 2.75rem | Hero-level vertical breathing room. |

---

## 8. Charte Graphique Amendly — Source de vérité (Gemini Canvas)

> **Cette section fait autorité.** En cas de contradiction avec la section 2, se référer à cette section.
> L'identité visuelle est centrée sur **la convergence, la précision et la validation**.

### Palette chromatique (tokens Tailwind)
| Token Tailwind | Hexadécimal | Usage |
| :--- | :--- | :--- |
| `amendly-blue` | `#2563EB` | Action principale, confiance, éléments de validation. |
| `amendly-dark` | `#0F172A` | Texte principal, titres forts, stabilité et professionnalisme. |
| `amendly-gray` | `#94A3B8` | Modifications, diffs, textes secondaires, bordures légères. |
| `amendly-light` | `#F8FAFC` | Arrière-plans d'interface, zones de survol, pureté. |

### Typographie (tokens Tailwind)
*   **`font-display`** : `Inter` (poids 700–900 / Black) — titres, headlines, logo, éléments display.
*   **`font-body`** : `Inter` (poids 400) — corps de texte, UI, labels.

> Inter remplace Manrope pour l'unification de la typographie (session 51).

### Règles d'application
*   Boutons CTA principaux : `bg-amendly-blue text-white`
*   Focus rings formulaires : `focus:ring-amendly-blue`
*   Liens inline : `text-secondary` (`#0053dc`)
*   Icônes colorées : `text-amendly-blue`