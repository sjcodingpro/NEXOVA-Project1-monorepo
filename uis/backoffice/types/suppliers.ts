export type Country = "Spain" | "USA";
export type Currency = "EUR" | "USD";
export type SupplierStatus = "active" | "suspended";

export type Category =
  | "job_boards"
  | "ats_software"
  | "assessment_tools"
  | "training_platforms"
  | "payroll_and_hr_software"
  | "video_interview"
  | "background_check"
  | "office_and_facilities"
  | "it_and_software_licenses";

export interface Supplier {
  id: number;
  name: string;
  country: Country;
  categories: Category[];
  monthly_rate: number;
  currency: Currency;
  status: SupplierStatus;
  contract_renewal_date: string | null;
  contact_email: string | null;
  notes: string | null;
  updated_at: string;
}

export interface CreateSupplierPayload {
  name: string;
  country: Country;
  categories: Category[];
  monthly_rate: number;
  currency: Currency;
  status: SupplierStatus;
  contract_renewal_date?: string | null;
  contact_email?: string | null;
  notes?: string | null;
}

export interface ApiErrorBody {
  detail: string | { msg: string }[];
}
