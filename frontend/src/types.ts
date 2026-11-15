export type Classification = "Advanced" | "Average" | "Needs Attention" | "No Data";

export interface Student {
  roll_no: string;
  name: string;
  marks: Record<string, number | null>;
  average: number | null;
  percentage: number | null;
  attendance: number | null;
  classification: Classification;
  missing_subjects: number;
}

export interface SubjectStat {
  subject: string;
  average: number | null;
  highest: number | null;
  lowest: number | null;
  count: number;
}

export interface Extreme {
  value: number;
  name: string;
  roll_no: string;
}

export interface Summary {
  total_students: number;
  evaluated_students: number;
  class_average: number | null;
  highest: Extreme | null;
  lowest: Extreme | null;
  attendance_average: number | null;
  attendance_count: number;
}

export interface Thresholds {
  advanced: number;
  attention: number;
}

export interface DetectedColumns {
  roll_no: string | null;
  name: string | null;
  attendance: string | null;
  subjects: string[];
  ignored: string[];
}

export interface ColumnMapping {
  roll_no: string | null;
  name: string | null;
  attendance: string | null;
  subjects: string[];
}

export interface Analysis {
  filename: string;
  max_marks: number;
  thresholds: Thresholds;
  columns: DetectedColumns;
  available_columns: string[];
  students: Student[];
  subject_stats: SubjectStat[];
  summary: Summary;
  distribution: Record<Classification, number>;
  warnings: string[];
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  columns?: string[];
  detected?: DetectedColumns;
}
