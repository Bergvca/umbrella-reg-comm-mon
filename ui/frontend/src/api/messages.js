import { apiFetch } from "./client";
export async function getAudioUrl(index, docId) {
    return apiFetch(`/messages/${index}/${docId}/audio`);
}
