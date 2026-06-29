import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatScore(score: number): string {
  return (score * 100).toFixed(1) + "%";
}

export function scoreColorClass(score: number): string {
  if (score >= 0.75) return "text-tertiary";
  if (score >= 0.5) return "text-secondary";
  return "text-error";
}

export function scoreBgClass(score: number): string {
  if (score >= 0.75) return "liquid-fill";
  if (score >= 0.5) return "liquid-fill-yellow";
  return "liquid-fill-risk";
}

export function trustScoreColor(score: number): string {
  if (score >= 75) return "bg-tertiary";
  if (score >= 50) return "bg-secondary";
  return "bg-error";
}

export function getCity(location: string): string {
  return location.split(",")[0].trim();
}

export const CAREER_DNA_COLORS: Record<string, string> = {
  "Startup Builder": "bg-tertiary/10 text-tertiary border-tertiary/25",
  "Scale Expert": "bg-secondary/15 text-primary border-secondary/25",
  "Product Engineer": "bg-primary-container/30 text-primary border-primary/20",
  "Research Specialist": "bg-tertiary-container/30 text-tertiary border-tertiary/30",
  "Consulting Only": "bg-error/10 text-error border-error/25",
};

export const CONFIDENCE_COLORS: Record<string, string> = {
  High: "bg-tertiary/10 text-tertiary border-tertiary/25",
  Medium: "bg-secondary/15 text-primary border-secondary/25",
  Low: "bg-error/10 text-error border-error/25",
};
