import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmt(v: number | null | undefined, digits = 0, suffix = "") {
  return v === null || v === undefined || !Number.isFinite(v) ? "—" : `${v.toFixed(digits)}${suffix}`;
}

export function snrLabel(snr: number | null | undefined) {
  if (snr === null || snr === undefined) return "—";
  if (snr >= 3) return "Good";
  if (snr >= 0) return "Fair";
  return "Poor";
}
