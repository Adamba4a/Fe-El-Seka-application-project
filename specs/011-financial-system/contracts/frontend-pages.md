# Frontend Page Contracts: Financial System (Phase 8)

**Branch**: `011-financial-system` | **Date**: 2026-06-29

---

## Driver Wallet Page

**Route**: `apps/main/src/app/(driver)/wallet/page.tsx`

**URL**: `/wallet` (under authenticated driver route group)

**Auth**: Requires active session with driver role. Redirects to login if unauthenticated.

**Data source**: `GET /drivers/me/wallet` — fetched server-side or client-side on mount; paginated on client.

### Layout

```
┌─────────────────────────────────────┐
│  My Wallet                          │
├─────────────────────────────────────┤
│  Available Balance      39.50 EGP   │
│  ─────────────────────────────────  │
│  Total balance:  47.50 EGP          │
│  Reserved:        8.00 EGP (2 rides)│
├─────────────────────────────────────┤
│  Transaction History                │
│  ─────────────────────────────────  │
│  [Commission Charge]  -2.00 EGP     │
│  Nasr City → Maadi · Jun 29, 14:23  │
│  ─────────────────────────────────  │
│  [Balance Top-Up]    +100.00 EGP    │
│  Jun 28, 10:00                      │
│  ─────────────────────────────────  │
│  ... (paginated)                    │
│  [Load more]                        │
└─────────────────────────────────────┘
```

### Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `WalletBalanceCard` | `components/wallet/WalletBalanceCard.tsx` | Shows available, total, and reserved figures prominently |
| `LedgerEntryList` | `components/wallet/LedgerEntryList.tsx` | Paginated list, 50 per page, newest-first |
| `LedgerEntryRow` | `components/wallet/LedgerEntryRow.tsx` | Type label, signed amount, ride link (for debits), timestamp |

### States

| State | Display |
|-------|---------|
| Loading | Skeleton cards for balance + list |
| No wallet (new driver) | 0.00 EGP balance, empty state message: "No transactions yet. Add balance to start posting rides." |
| Balance present, no reservations | Available = Total; no reserved row shown |
| Balance present, with reservations | All three figures shown (total, reserved, available) |
| Error (API failure) | Toast error; retry button |

### Interaction Rules

- Balance figures update after returning from ride creation if reservation was created (page refetch on focus)
- "Commission Charge" entries link to the associated ride detail page
- Pagination is "Load More" style (append), not page-number navigation
- All EGP amounts formatted as `#,##0.00 EGP` (e.g., `1,234.50 EGP`)
- Credits shown with `+` prefix and green colour; debits with `-` prefix and red colour

---

## Admin Driver Wallet Page

**Route**: `apps/admin/src/app/(dashboard)/drivers/[id]/wallet/page.tsx`

**URL**: `/drivers/{id}/wallet` (within authenticated admin dashboard)

**Auth**: Requires active session with admin role. Redirects to login if unauthenticated.

**Data source**: `GET /admin/drivers/{id}/wallet` (reads same data as driver endpoint but via admin API — or reuses the driver endpoint on behalf of the driver). Top-up and adjust call their respective admin endpoints.

### Layout

```
┌─────────────────────────────────────────┐
│  Ahmed Mohamed — Wallet Management      │
├─────────────────────────────────────────┤
│  Balance:    47.50 EGP                  │
│  Reserved:    8.00 EGP                  │
│  Available:  39.50 EGP                  │
├─────────────────────────────────────────┤
│  [Top Up Wallet]        [Adjust Balance]│
├─────────────────────────────────────────┤
│  Top-Up Form (expandable)               │
│  Amount: [______] EGP                   │
│  Note:   [___________________________]  │
│  [Confirm Top-Up]                        │
├─────────────────────────────────────────┤
│  Transaction Ledger                     │
│  ─────────────────────────────────────  │
│  COMMISSION_DEBIT  -2.00 EGP  Jun 29   │
│  Ride: Nasr City → Maadi               │
│  ─────────────────────────────────────  │
│  ADMIN_CREDIT     +100.00 EGP  Jun 28  │
│  By: admin@platform.com                 │
│  Note: Initial top-up                   │
└─────────────────────────────────────────┘
```

### Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `AdminWalletSummary` | `components/wallet/AdminWalletSummary.tsx` | Three balance figures (total, reserved, available) |
| `TopUpForm` | `components/wallet/TopUpForm.tsx` | Amount + note input; calls `POST /admin/…/topup`; shows success/error |
| `AdjustForm` | `components/wallet/AdjustForm.tsx` | Amount + note input; calls `POST /admin/…/adjust`; shows max-debit hint |
| `AdminLedgerTable` | `components/wallet/AdminLedgerTable.tsx` | Full ledger; shows `created_by` admin email; all entry types |

### States

| State | Display |
|-------|---------|
| Top-up success | Green toast: "Wallet topped up by 200.00 EGP. New balance: 247.50 EGP." Balance figures reload. |
| Top-up error (invalid amount) | Inline field error: "Amount must be greater than 0." |
| Adjust success | Green toast: "Balance adjusted by -50.00 EGP. New available balance: 197.50 EGP." |
| Adjust error (exceeds available) | Inline error: "Maximum debit is 39.50 EGP (driver has 8.00 EGP reserved for active rides)." |
| No wallet | 0.00 EGP balances displayed; top-up still works (creates wallet). |

### Interaction Rules

- Both forms are inline (accordion expand), not modals — faster to act on
- After any successful mutation, wallet summary refetches immediately
- Top-up form defaults amount field to empty (no pre-fill to avoid accidental large credits)
- Adjust form shows current available balance as hint: "Max debit: 39.50 EGP"
- Ledger table shows admin actor email (resolved from `created_by` UUID) for ADMIN_CREDIT/ADMIN_DEBIT rows
- All EGP amounts formatted consistently with driver view (`#,##0.00 EGP`)
