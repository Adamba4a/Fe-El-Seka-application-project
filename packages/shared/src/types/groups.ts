export type GroupType = "general" | "company" | "university";

export interface Group {
  id: string;
  name: string;
  type: GroupType;
  description: string | null;
  route_tags: string[];
  member_count: number;
}

export interface GroupDetail extends Group {
  is_member: boolean;
  is_owner: boolean;
}

export interface GroupListResponse {
  items: Group[];
  total: number;
}

export interface CreateGroupPayload {
  name: string;
  description?: string;
  route_tags?: string[];
}
