import { useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import type { AlertOut, PaginatedResponse } from "@/lib/types";

/**
 * Provides keyboard navigation (j/k, ArrowLeft/ArrowRight) between alerts
 * using the cached alert list from TanStack Query.
 */
export function useAlertNavigation(currentAlertId: string) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const getAdjacentAlertIds = useCallback(() => {
    // Find the most recent cached alert list query
    const queries = queryClient.getQueriesData<PaginatedResponse<AlertOut>>({
      queryKey: ["alerts", "list"],
    });

    for (const [, data] of queries) {
      if (!data?.items) continue;
      const idx = data.items.findIndex((a) => a.id === currentAlertId);
      if (idx === -1) continue;
      return {
        prevId: idx > 0 ? data.items[idx - 1].id : null,
        nextId: idx < data.items.length - 1 ? data.items[idx + 1].id : null,
        position: idx + 1,
        total: data.items.length,
      };
    }

    return { prevId: null, nextId: null, position: null, total: null };
  }, [currentAlertId, queryClient]);

  const nav = getAdjacentAlertIds();

  const goToPrev = useCallback(() => {
    if (nav.prevId) navigate(`/alerts/${nav.prevId}`);
  }, [nav.prevId, navigate]);

  const goToNext = useCallback(() => {
    if (nav.nextId) navigate(`/alerts/${nav.nextId}`);
  }, [nav.nextId, navigate]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't intercept when user is typing in an input/textarea
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if ((e.target as HTMLElement).isContentEditable) return;

      if (e.key === "k" || e.key === "ArrowLeft") {
        e.preventDefault();
        goToPrev();
      } else if (e.key === "j" || e.key === "ArrowRight") {
        e.preventDefault();
        goToNext();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [goToPrev, goToNext]);

  return {
    prevId: nav.prevId,
    nextId: nav.nextId,
    position: nav.position,
    total: nav.total,
    goToPrev,
    goToNext,
  };
}
