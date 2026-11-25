export interface MedicineSearchItem {
  id: number;
  registrationNumber?: string | null;
  nationalCode?: string | null;
  brandName: string;
  genericName?: string | null;
  strength?: string | null;
  pharmaceuticalForm?: string | null;
  packaging?: string | null;
  laboratory?: string | null;
  country?: string | null;
  isActive: boolean;
  sourceVersion?: string | null;
}

export interface MedicineSearchResponse {
  items: MedicineSearchItem[];
  total: number;
}

export interface MedicineImportRecord {
  id: number;
  file_name: string;
  original_file_name: string;
  file_hash: string;
  source_name: string;
  source_version?: string | null;
  import_mode: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  inserted_rows: number;
  updated_rows: number;
  unchanged_rows: number;
  skipped_rows: number;
  invalid_rows: number;
  duplicate_rows: number;
  deactivated_rows: number;
  mapping_json?: Record<string, string> | null;
  summary_json?: Record<string, unknown> | null;
  error_message?: string | null;
  notes?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MedicineImportPreview {
  importId: number;
  status: string;
  sheetNames: string[];
  detectedSheet?: string | null;
  detectedHeaderRow?: number | null;
  detectedColumns: string[];
  selectedMapping: Record<string, string>;
  totalRows: number;
  validRows: number;
  invalidRows: number;
  duplicateRows: number;
  potentialInserts: number;
  potentialUpdates: number;
  unchangedRows: number;
  warnings: string[];
  sampleRows: Array<{
    row_number?: number | null;
    values: Record<string, unknown>;
  }>;
  errors: Array<{
    id: number;
    medicine_import_id: number;
    sheet_name?: string | null;
    row_number?: number | null;
    field_name?: string | null;
    raw_value?: string | null;
    error_code: string;
    error_message: string;
  }>;
}
