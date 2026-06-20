# Contract: Design Tokens

**Feature**: `006-frontend-design` | **Date**: 2026-06-20

This document is the authoritative definition of all design tokens for `apps/main`. Any value not listed here MUST NOT appear as a hardcoded color, font size, or spacing override in any component or screen file.

---

## CSS Custom Properties (`apps/main/src/app/globals.css`)

```css
:root {
  /* Brand */
  --color-brand-primary:          #1B3A6B;
  --color-brand-primary-hover:    #2D5AA8;
  --color-brand-accent:           #E8A217;

  /* Surfaces */
  --color-surface-bg:             #F8F9FA;
  --color-surface-card:           #FFFFFF;
  --color-surface-overlay:        rgba(0, 0, 0, 0.50);

  /* Text */
  --color-text-primary:           #111827;
  --color-text-secondary:         #374151;
  --color-text-muted:             #6B7280;
  --color-text-destructive:       #DC2626;

  /* Borders */
  --color-border-default:         #E5E7EB;
  --color-border-focus:           #2D5AA8;

  /* Status — text/icon */
  --color-status-scheduled:       #2563EB;
  --color-status-in-progress:     #D97706;
  --color-status-completed:       #16A34A;
  --color-status-cancelled:       #DC2626;

  /* Status — badge backgrounds */
  --color-status-scheduled-bg:    #DBEAFE;
  --color-status-in-progress-bg:  #FEF3C7;
  --color-status-completed-bg:    #DCFCE7;
  --color-status-cancelled-bg:    #FEE2E2;
}
```

---

## Tailwind Theme Extension (`apps/main/tailwind.config.ts`)

```ts
theme: {
  extend: {
    colors: {
      brand: {
        primary:       'var(--color-brand-primary)',
        'primary-hover': 'var(--color-brand-primary-hover)',
        accent:        'var(--color-brand-accent)',
      },
      surface: {
        bg:      'var(--color-surface-bg)',
        card:    'var(--color-surface-card)',
        overlay: 'var(--color-surface-overlay)',
      },
      content: {
        primary:     'var(--color-text-primary)',
        secondary:   'var(--color-text-secondary)',
        muted:       'var(--color-text-muted)',
        destructive: 'var(--color-text-destructive)',
      },
      border: {
        default: 'var(--color-border-default)',
        focus:   'var(--color-border-focus)',
      },
      status: {
        scheduled:       'var(--color-status-scheduled)',
        'in-progress':   'var(--color-status-in-progress)',
        completed:       'var(--color-status-completed)',
        cancelled:       'var(--color-status-cancelled)',
        'scheduled-bg':  'var(--color-status-scheduled-bg)',
        'in-progress-bg':'var(--color-status-in-progress-bg)',
        'completed-bg':  'var(--color-status-completed-bg)',
        'cancelled-bg':  'var(--color-status-cancelled-bg)',
      },
    },
    fontSize: {
      h1:       ['1.875rem', { lineHeight: '1.2', fontWeight: '700' }],
      h2:       ['1.5rem',   { lineHeight: '1.3', fontWeight: '700' }],
      h3:       ['1.25rem',  { lineHeight: '1.3', fontWeight: '600' }],
      body:     ['1rem',     { lineHeight: '1.5', fontWeight: '400' }],
      'body-sm':['0.875rem', { lineHeight: '1.5', fontWeight: '400' }],
      caption:  ['0.75rem',  { lineHeight: '1.4', fontWeight: '400' }],
      label:    ['0.875rem', { lineHeight: '1',   fontWeight: '500' }],
    },
  },
},
```

---

## Usage Rules

1. Use `text-content-primary` not `text-gray-900`.
2. Use `bg-surface-card` not `bg-white`.
3. Use `border-border-default` not `border-gray-200`.
4. Use `text-brand-primary` not `text-blue-700`.
5. Use `text-status-scheduled` / `bg-status-scheduled-bg` for `RideStatusBadge` — never `text-blue-800` / `bg-blue-100`.
6. The `bg-surface-overlay` token is semi-transparent (`rgba(0,0,0,0.5)`) — do not apply additional opacity utilities on top of it.

---

## Validation

Run this grep to verify no hardcoded colors remain after implementation:

```bash
grep -rE '(#[0-9a-fA-F]{3,6}|text-(gray|blue|red|green|yellow|amber|orange|purple)-[0-9]+|bg-(gray|blue|red|green|yellow|amber|orange|purple)-[0-9]+)' apps/main/src/components apps/main/src/app
```

Expected result: zero matches (only token-named classes appear).
