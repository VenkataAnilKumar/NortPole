export type RouteKind = "local" | "private" | "cloud";
export type DataClass = "public" | "internal" | "confidential" | "restricted";

export interface RouteView {
  provider_id: number;
  name: string | null;
  provider: string;
  model_names: string[];
  kind: RouteKind;
  /** False when an administrator has not set this route's type yet. */
  kind_assigned: boolean;
  allowed: boolean;
  reason: string | null;
}

export interface RoutePolicyView {
  version: number;
  data_class: DataClass;
  default_data_class: DataClass;
  data_classes: DataClass[];
  route_kinds: RouteKind[];
  allowed: Record<DataClass, RouteKind[]>;
  redact_route_kinds?: RouteKind[];
  routes: RouteView[];
  auto_provider_id: number | null;
}
