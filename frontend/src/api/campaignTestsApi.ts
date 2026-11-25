// frontend/src/api/campaignTestsApi.ts

import apiClient from "./axios";
import type { CampaignTestAssignment } from "@/types/entities";

export type CampaignTest = {
  id?: number;
  campaign_test_id?: number;
  campaign_id?: number;
  test_id: number;
  name?: string | null;
  description?: string | null;
  type?: string | null;
  required: boolean;
  created_at?: string;
  updated_at?: string;
};

export type CampaignTestPayload = {
  test_id: number;
  required: boolean;
};

const normalizeCampaignTests = (items: Array<Record<string, unknown>>) =>
  items.map((item) => ({
    ...item,
    id: item.id ? Number(item.id) : undefined,
    campaign_test_id: item.campaign_test_id ? Number(item.campaign_test_id) : undefined,
    campaign_id: item.campaign_id ? Number(item.campaign_id) : undefined,
    test_id: Number(item.test_id),
    name: typeof item.name === "string" ? item.name : null,
    description: typeof item.description === "string" ? item.description : null,
    type: typeof item.type === "string" ? item.type : null,
    required: Boolean(item.required),
  })) as CampaignTest[];

export const getCampaignTests = async (
  campaignId: number | string,
): Promise<CampaignTest[]> => {
  const { data } = await apiClient.get<CampaignTestAssignment[]>(
    `/campaigns/${campaignId}/tests`,
  );

  return normalizeCampaignTests(data as unknown as Array<Record<string, unknown>>);
};

export const createCampaignTests = async (
  campaignId: number | string,
  payload: CampaignTestPayload[],
): Promise<CampaignTest[]> => {
  const { data } = await apiClient.post<CampaignTestAssignment[]>(
    `/campaigns/${campaignId}/tests`,
    payload,
  );

  return normalizeCampaignTests(data as unknown as Array<Record<string, unknown>>);
};

export const saveCampaignTests = async (
  campaignId: number | string,
  payload: CampaignTestPayload[],
): Promise<CampaignTest[]> => {
  const { data } = await apiClient.put<CampaignTestAssignment[]>(
    `/campaigns/${campaignId}/tests`,
    payload,
  );

  return normalizeCampaignTests(data as unknown as Array<Record<string, unknown>>);
};

export const deleteCampaignTest = async (
  campaignId: number | string,
  testId: number | string,
) => {
  const { data } = await apiClient.delete(
    `/campaigns/${campaignId}/tests/${testId}`,
  );

  return data;
};
