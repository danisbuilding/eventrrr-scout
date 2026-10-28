# Neue Verdant — developer handoff
Version 1.0 · 28 October 2026

## 1. What to build

Build an event-data review dashboard using the included reference.png as the visual target. The approved direction is **Neue / Verdant with light shading**: a pure white canvas, slim Swiss-style typography, restrained botanical green accents, fine architectural rules, and subtle local depth.

This is a data-review tool for its owner. Prioritize scanning rows, inspecting extracted fields, correcting data, resolving duplicates, and publishing approved events. Maintain purposeful whitespace without making titles, cards, or imagery dominate the screen.

**Status of this specification:** The reference is an AI-generated raster mockup, not a Figma file or an implemented UI. It does not embed verifiable font-family names, CSS, component measurements, or source colors. The values below are explicit implementation targets interpreted from the approved image. Use these tokens consistently rather than sampling every antialiased pixel. Validate the first implemented screen against the reference before expanding the app.

## 2. Approved visual decisions

- White #FFFFFF app canvas, header, inspector, inputs and unselected rows.
- Botanical green primary actions, active navigation, source links, selection marker and checked boxes.
- Dark navy-black primary text; muted slate secondary text.
- Small, light headings and compact readable body text.
- Eight rows visible at the reference desktop size; no mandatory row count on smaller screens.
- Broad event table on the left; text-only event inspector on the right.
- One vertical rule between the two regions, fine horizontal row/section dividers.
- Local shading on the selected row, inspector boundary, controls and buttons.
- Very modest 4px control radii. No rounded dashboard cards.
- No large images, hero sections, decorative charts, all-screen gradients, glass effects, or heavy shadows.
- The top strip reading “02 — NEUE / VERDANT” is a presentation annotation: **do not ship it in the app**.
- “Gather” is a working product name; it can be replaced without changing the design system.

## 3. Color tokens

All values are sRGB CSS colors. These are normalized implementation values, not claims of exact source-image pixel values.

| CSS token | Value | Role |
|---|---|---|
| --nv-canvas | #FFFFFF | All main surfaces |
| --nv-ink | #172033 | Headings, event names, data values |
| --nv-muted | #626D88 | Secondary labels and metadata |
| --nv-green | #2E6957 | Primary accent, active nav, links, checkboxes |
| --nv-green-top | #377C63 | Very subtle button top shading |
| --nv-green-deep | #285E4E | Button lower edge and hover |
| --nv-line | #E2E7ED | Fine structural rules |
| --nv-control-line | #D5DCE5 | Inputs and secondary-button outlines |
| --nv-ready | #2F8068 | Ready / online status dot |
| --nv-review | #8A6447 | Needs-review status dot |
| --nv-duplicate | #A77C00 | Duplicate status dot |
| --nv-neutral | #7C8494 | Inactive / unknown status dot |
| --nv-selected-start | rgba(46,105,87,.055) | Selected-row shading start |
| --nv-selected-end | rgba(46,105,87,.018) | Selected-row shading end |

Keep button labels white. Keep status text in --nv-ink or --nv-muted; the colored dot is supplemental. Do not use tiny gold text for duplicate warnings. Do not make all statuses green simply because the brand color is green.

Calculated contrast against white: --nv-ink approximately 16:1, --nv-muted 5.17:1, and --nv-green 6.41:1. White labels on the lighter button top #377C63 are approximately 4.97:1. These are token-pair checks, not a complete accessibility audit.

## 4. Typography

### Intended font system

**Headings and wordmark:** Neue Haas Grotesk Display, 45 Light, mapped to CSS weight 300.
**UI/data:** Neue Haas Grotesk Text, Roman/Regular, mapped to CSS weight 400.

The “45” and “55” style names used by some font distributions are not literal CSS font-weight values. Map the licensed files to normal CSS weights in @font-face. Use genuine light and regular files, not synthetic thinning.

Use the Display cut for large text and Text cut for small UI/data. The family chosen in the image-generation prompt was Neue Haas Grotesk, but its exact rendering in the image cannot be verified.

Font availability and web-use permissions should be confirmed with the font supplier. Do not assume a desktop font entitlement permits self-hosted web fonts. No font binaries are included in this package.

**Free substitute if avoiding a commercial font purchase:** Inter Variable, 300 for headings and 400 for body. This is a deliberate substitute and will change letterforms and line breaks slightly. Do not silently mix several unrelated sans-serif families across the UI.

Official resources:
- Display family: https://commercialtype.com/catalog/neue_haas_grotesk/neue_haas_grotesk_display
- Text family: https://commercialtype.com/catalog/neue_haas_grotesk/neue_haas_grotesk_text
- Inter: https://rsms.me/inter/

### Type scale at a 1440px desktop viewport

| Role | Size / line-height | Weight | Tracking |
|---|---|---|---|
| Wordmark | 28 / 34px | 300 | -0.025em |
| Page title | 32 / 40px | 300 | -0.025em |
| Inspector event title | 28 / 36px | 300 | -0.02em |
| Event-row name | 14 / 20px | 400 | -0.01em |
| UI body / values | 13 / 20px | 400 | 0 |
| Button / input label | 13 / 18px | 400 | 0 |
| Small metadata | 12 / 18px | 400 | 0 |
| Dates and time | 12 / 18px | 400 | 0 |
| Uppercase section/column label | 10 / 16px | 400 | 0.12em |
| Metric value | 16 / 22px | 400 | -0.015em |

The reference shows a technical, nearly monospaced date treatment. For dates/times only, use a system monospace stack at 12px, or use the UI font with tabular numerals if closer visual matching requires it. Do not change the rest of the app to monospace.

Avoid 100/200-weight body text, bold headlines, large dashboard numerals, serif headings, and enlarged type intended to fill space. Preserve readable text rather than making every element equally thin.

## 5. Layout and spacing

Reference asset: 1586 × 992px. Recommended implementation baseline: 1440 × 900 CSS pixels. The proportions and hierarchy matter more than matching image pixels one-for-one.

### Desktop: 1280px and above

- App header: 72px high, 1px bottom rule, 40px horizontal padding.
- Gather wordmark left; Events / Sources / Categories navigation next; scan action, freshness and account at right.
- Main content: 40px outer horizontal gutters, 32px top padding.
- Workspace: flexible table column + 400px inspector; 24px inter-column gap.
- Inspector: 1px left border, 32px left padding, 24px right padding; white surface.
- Table side header: title, then quiet inline totals, then 24–28px gap before toolbar.
- Metrics: inline values and labels separated by short vertical rules; no KPI cards.
- Toolbar controls: 36px high; search about 320px; category/source filters about 175px each; 12px gaps. Let the toolbar adapt rather than overflow.
- Table header: 36px; rows approximately 58px minimum with 12px vertical padding. Permit height to grow for long content.
- Row name: single line where possible. Date and time may occupy two lines.
- Table cell horizontal padding: 12px. Check column: 32px; trailing chevron: 24px.
- Suggested remaining column allocation: name 22%, category 18%, date/time 21%, source 19%, status 20%. Adapt to actual strings; do not crop essential review states.
- Table footer: 24px gap above it; Publish selected and selected-count left, pagination right.
- Inspector fields: a label/value grid, approximately 112px label column, 12px gap; 16–20px between fields.
- Inspector action row: primary Approve event + secondary Edit, 12px gap; 40px control height.
- Source information below actions: fine horizontal divider, 24px section spacing.
- Table and inspector may scroll independently only when a constrained app viewport requires it. Prefer a sticky inspector with its own overflow for long detail content.

Spacing scale: **4, 8, 12, 16, 20, 24, 32, 40, 48px**. Use 1px rules, 4px default radius, 16px line icons and 8px status dots.

### Below 1280px

Use the full content width for the table. Open the inspector as an accessible right drawer rather than squeezing every column. Maintain the same type scale and styling. Tablet drawers can be around 400–440px wide.

### Below 768px

Use 16px outer gutters; let toolbar controls wrap. Keep a scrollable data table with a minimum width rather than silently hiding critical fields. Open event detail as a full-width dialog/view. A compact navigation menu can replace the desktop nav. Increase actionable touch areas where needed without inflating all typography.

These responsive behaviors are proposed implementation rules; only the desktop state is shown in the reference.

## 6. Shading and borders

Depth is local. The main canvas remains pure white.

- **Primary button:** a subtle vertical green gradient from #377C63 through #2E6957 to #285E4E; a 1px white inset top edge at 12% opacity; a low-opacity green contact shadow.
- **Secondary button/input:** white fill, 1px --nv-control-line, very soft underside shadow.
- **Selected row:** fine 2px green left marker plus a very faint left-to-right green tint fading toward white. Other rows stay white.
- **Inspector boundary:** a narrow feathered neutral shadow along its left edge, limited to that boundary. Avoid shading the whole inspector.
- **Rows/sections:** plain 1px --nv-line. Do not outline every cell.

Do not animate shadows constantly or make controls look glossy. Motion, where useful, should be approximately 140ms ease-out for color/shadow changes, with reduced-motion support.

## 7. Components and behavior

| Component | Default / visual | Interaction contract |
|---|---|---|
| Navigation | Small text; active green underline | Mark current page; do not use color alone |
| Scan sources | Primary green button | Show Scanning… and progress/status; prevent duplicate concurrent requests; report partial failures without clearing current data |
| Search | White outlined input with 16px search icon | Filter results; show clear/search-empty states |
| Filters | Category and source dropdowns | Show active values; support reset; retain current filters when opening/closing detail |
| Queue row | White with bottom rule | Selecting the name or chevron opens the inspector; checkbox only changes bulk selection |
| Current row | Faint green tint + left marker | Current inspected row and bulk checkbox selection are independent states |
| Bulk selection | Native checkbox visual, green when checked | Header checkbox selects visible filtered page; show indeterminate state; bulk actions say how many events |
| Status | 8px dot + visible text | Ready, Needs review and Duplicate remain distinguishable without color |
| Inspector | White; label/value pairs | Show source URL, extracted values, price/currency, dates and confidence; allow editing before approval |
| Approve event | Primary green action | Validate required fields; mark event approved. If already approved, show Approved and prevent redundant requests |
| Edit | Secondary outlined action | Edit fields with explicit save/cancel; retain inspector context |
| Publish selected | Primary green action | Enable only when selected records are eligible; clearly explain unresolved records; show progress and completion |
| Confidence | Plain percentage in metadata | Display only a meaningful score supplied by the pipeline; show unavailable when no score exists |
| Source health | Status + last scan + link | Preserve stale-data timestamps and distinguish offline from failed extraction |
| Pagination | Small outlined arrow controls | Visible page information; disabled arrows at boundaries; preserve filters |

Approval means reviewed/accepted. Publishing means live on the event site. Model them separately.

The screenshot's ready label plus enabled Approve button is illustrative, not a state-machine requirement. Correct that inconsistency in the implementation.

Provide first-class loading, no-results, no-events-yet, scan failure, source failure and publish failure states. Preserve existing rows during background refresh. Show inline field errors near the field. Do not replace the screen with a giant spinner.

Use local source-event dates and a visible/known event timezone; do not silently convert event times to the operator's timezone. Display prices with currency, not an ambiguous bare dollar sign. Counts such as duplicates can overlap other states; do not assume the four metrics must sum.

## 8. Interaction and readability details

- Use semantic tables, real buttons, labelled inputs and keyboard-operable controls.
- Do not make the entire row a button containing checkboxes/buttons. Use a normal table with an accessible event-name button/link and separate checkbox.
- 2px green focus outline with 2px offset on interactive controls; preserve visible keyboard focus.
- Keep column labels programmatically associated with cells and label row checkboxes with event names.
- Icon-only controls need accessible names; drawers/dialogs need focus management and an obvious close action.
- Present state changes and scan/publish completion through an appropriate live status region.
- Provide a clear non-color indicator for selected rows and statuses. Do not rely on a near-white fill alone.
- Allow browser zoom and text resizing. Let real strings wrap where needed.
- Keep small text regular-weight if light rendering becomes weak on non-Retina displays.
- Hover should be subtle; pressed, disabled, focus and error states must be designed, not left to browser accident.

## 9. Implementation files and acceptance

Included:
- reference.png — exact selected visual reference.
- neue-verdant.css — semantic tokens and reusable starter component styles; framework-agnostic, not a complete app.
- design-system.md — this specification.
- README.md — how to use the package.

No licensed fonts, production app code, real event data, or editable Figma file are included.

First implementation checkpoint: recreate this one desktop review screen with realistic-length data and an open inspector. Compare white background, light heading weight, green buttons, selected row, table density and boundary shading against reference.png. Check keyboard operation and the proposed drawer behavior once. Then apply the same components to Sources, Categories and other screens.

Use this spec's exact tokens as the implementation source of truth. Treat font mapping and responsive behavior as explicit engineering choices, not details recoverable perfectly from a generated screenshot.
