import type { Analysis, ApiErrorDetail, ColumnMapping, DetectedColumns, Thresholds } from "./types";

const raw = import.meta.env.VITE_API_URL;
export const API_URL = (raw && raw.trim() ? raw.trim() : "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  code: string;
  columns?: string[];
  detected?: DetectedColumns;

  constructor(detail: ApiErrorDetail) {
    super(detail.message);
    this.name = "ApiError";
    this.code = detail.code;
    this.columns = detail.columns;
    this.detected = detail.detected;
  }
}

function buildForm(file: File, thresholds: Thresholds, mapping: ColumnMapping | null): FormData {
  const form = new FormData();
  form.append("file", file);
  form.append("advanced_threshold", String(thresholds.advanced));
  form.append("attention_threshold", String(thresholds.attention));
  if (mapping) form.append("mapping", JSON.stringify(mapping));
  return form;
}

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body: unknown = await res.json();
    const detail = (body as { detail?: unknown }).detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail) && "message" in detail) {
      return new ApiError(detail as ApiErrorDetail);
    }
    if (typeof detail === "string") return new ApiError({ code: `HTTP_${res.status}`, message: detail });
    if (Array.isArray(detail)) {
      const msg = detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ");
      return new ApiError({ code: "VALIDATION_ERROR", message: msg || "The request was not valid." });
    }
  } catch {
    // body was not JSON – fall through
  }
  return new ApiError({ code: `HTTP_${res.status}`, message: `The server returned an unexpected response (${res.status}).` });
}

async function post(path: string, form: FormData): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: "POST", body: form });
  } catch {
    throw new ApiError({
      code: "NETWORK",
      message: `Could not reach the PRISM server at ${API_URL}. Check that the backend is running and that CORS_ORIGINS allows this site. If it is hosted on a free tier it may need up to a minute to wake up.`,
    });
  }
  if (!res.ok) throw await toApiError(res);
  return res;
}

export async function analyzeFile(file: File, thresholds: Thresholds, mapping: ColumnMapping | null): Promise<Analysis> {
  const res = await post("/api/analyze", buildForm(file, thresholds, mapping));
  return (await res.json()) as Analysis;
}

export async function exportWorkbook(file: File, thresholds: Thresholds, mapping: ColumnMapping | null): Promise<Blob> {
  const res = await post("/api/export", buildForm(file, thresholds, mapping));
  return await res.blob();
}
