import { apiFetch } from "./client";
import type { GenerationJobCreate, GenerationJobOut } from "@/lib/types";

export async function getDefaultQuery(): Promise<{ default_kql: string }> {
  return apiFetch("/alert-generation/default-query");
}

export async function createGenerationJob(body: GenerationJobCreate): Promise<GenerationJobOut> {
  return apiFetch("/alert-generation/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listGenerationJobs(): Promise<GenerationJobOut[]> {
  return apiFetch("/alert-generation/jobs");
}

export async function getGenerationJob(id: string): Promise<GenerationJobOut> {
  return apiFetch(`/alert-generation/jobs/${id}`);
}

export async function syncRules(): Promise<{ upserted: number; errors: number }> {
  return apiFetch("/alert-generation/sync-rules", { method: "POST" });
}
