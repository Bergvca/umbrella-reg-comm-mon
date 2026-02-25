import { apiFetch } from "./client";
import type { ESMessage, MessageSearchResponse, NLSearchResponse } from "@/lib/types";

export interface AudioUrlResponse {
  url: string;
  expires_in: number;
}

export interface MessageSearchParams {
  q?: string;
  channel?: string;
  direction?: string;
  participant?: string;
  date_from?: string;
  date_to?: string;
  sentiment?: string;
  risk_score_min?: number;
  offset?: number;
  limit?: number;
}

export async function searchMessages(
  params: MessageSearchParams = {},
): Promise<MessageSearchResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.channel) sp.set("channel", params.channel);
  if (params.direction) sp.set("direction", params.direction);
  if (params.participant) sp.set("participant", params.participant);
  if (params.date_from) sp.set("date_from", params.date_from);
  if (params.date_to) sp.set("date_to", params.date_to);
  if (params.sentiment) sp.set("sentiment", params.sentiment);
  if (params.risk_score_min != null)
    sp.set("risk_score_min", String(params.risk_score_min));
  sp.set("offset", String(params.offset ?? 0));
  sp.set("limit", String(params.limit ?? 20));
  return apiFetch(`/messages/search?${sp.toString()}`);
}

export async function nlSearchMessages(body: {
  query: string;
  offset?: number;
  limit?: number;
}): Promise<NLSearchResponse> {
  return apiFetch<NLSearchResponse>("/messages/nl-search", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getMessage(
  index: string,
  docId: string,
): Promise<ESMessage> {
  return apiFetch(`/messages/${index}/${docId}`);
}

export async function getAudioUrl(
  index: string,
  docId: string,
): Promise<AudioUrlResponse> {
  return apiFetch(`/messages/${index}/${docId}/audio`);
}
