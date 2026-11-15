import type { Classification } from "./types";

export const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;

export const CLASS_ORDER: Classification[] = ["Advanced", "Average", "Needs Attention", "No Data"];

export const CLASS_COLORS: Record<Classification, string> = {
  Advanced: "#059669",
  Average: "#2563eb",
  "Needs Attention": "#dc2626",
  "No Data": "#9ca3af",
};

export const CLASS_SLUG: Record<Classification, string> = {
  Advanced: "adv",
  Average: "avg",
  "Needs Attention": "need",
  "No Data": "none",
};

export const PRIMARY = "#6d28d9";
