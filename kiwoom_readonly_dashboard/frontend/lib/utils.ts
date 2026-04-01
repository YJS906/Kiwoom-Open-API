import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function toWsUrl(apiBaseUrl: string) {
  return apiBaseUrl.replace(/^http/i, "ws") + "/ws/stream";
}
