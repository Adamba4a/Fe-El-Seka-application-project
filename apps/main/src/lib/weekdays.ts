// UI weekday indices are 0=Sunday..6=Saturday (matches the weekdayShort.{n}
// translation keys). The API stores ISO weekday numbers, 1=Monday..7=Sunday.
// Convert only at the API boundary — UI state and translation lookups stay
// in the 0-6 (Sunday-first) form throughout the components.
export function toIsoWeekday(uiDay: number): number {
  return uiDay === 0 ? 7 : uiDay;
}

export function fromIsoWeekday(isoDay: number): number {
  return isoDay === 7 ? 0 : isoDay;
}
