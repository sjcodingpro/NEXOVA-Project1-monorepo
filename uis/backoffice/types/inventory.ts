export type Category = "hardware" | "peripherals" | "office_supplies" | "training_materials";
export type Office = "Valencia" | "Miami";
export type ExitType = "allocation" | "consumption";

export interface Asset {
  id: number;
  name: string;
  sku: string;
  category: Category;
  office: Office;
  current_stock: number;
}

export interface AssetCreatePayload {
  name: string;
  sku: string;
  category: Category;
  office: Office;
}

export interface AssetEntry {
  id: number;
  asset_id: number;
  quantity: number;
  supplier: string;
  office: Office;
  created_at: string;
  user_uuid: string;
}

export interface AssetEntryCreatePayload {
  asset_id: number;
  quantity: number;
  supplier: string;
  office: Office;
}

export interface AssetExit {
  id: number;
  asset_id: number;
  quantity: number;
  exit_type: ExitType;
  assigned_to: string | null;
  office: Office;
  created_at: string;
  user_uuid: string;
}

export interface AssetExitCreatePayload {
  asset_id: number;
  quantity: number;
  exit_type: ExitType;
  assigned_to?: string | null;
  office: Office;
}

// Matches GET /inventory/orders' combined entries+exits listing.
export interface Order {
  order_type: "inbound" | "outbound";
  id: number;
  asset_id: number;
  asset_name: string;
  asset_sku: string;
  quantity: number;
  office: Office;
  created_at: string;
  user_uuid: string;
  supplier: string | null;
  exit_type: ExitType | null;
  assigned_to: string | null;
}
