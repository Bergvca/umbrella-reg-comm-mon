import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/stores/auth";
import { executeAgentStream, agentRunStreamUrl, cancelAgentRun, getAgentRun } from "@/api/agents";
import { ApiError } from "@/api/client";
export function useAgentStream(agentId) {
    const [runs, setRuns] = useState([]);
    const [currentRunId, setCurrentRunId] = useState(null);
    const [isStreaming, setIsStreaming] = useState(false);
    const eventSourceRef = useRef(null);
    const updateCurrentRun = useCallback((updater) => {
        setRuns((prev) => prev.map((r, i) => (i === prev.length - 1 ? updater(r) : r)));
    }, []);
    const startRun = useCallback(async (input) => {
        if (isStreaming)
            return;
        let result;
        try {
            result = await executeAgentStream({ agent_id: agentId, input });
        }
        catch (err) {
            let errorMessage = "Failed to start agent run";
            if (err instanceof ApiError) {
                const detail = err.body?.detail;
                errorMessage = detail
                    ? `${detail} (HTTP ${err.status})`
                    : `Server error ${err.status}`;
            }
            else if (err instanceof Error) {
                errorMessage = err.message;
            }
            const failedRun = {
                runId: crypto.randomUUID(),
                input,
                status: "failed",
                steps: [],
                output: null,
                errorMessage,
                totalTokens: null,
                durationMs: null,
                iterations: null,
            };
            setRuns((prev) => [...prev, failedRun]);
            return;
        }
        const runId = result.run_id;
        const newRun = {
            runId,
            input,
            status: "running",
            steps: [],
            output: null,
            errorMessage: null,
            totalTokens: null,
            durationMs: null,
            iterations: null,
        };
        setRuns((prev) => [...prev, newRun]);
        setCurrentRunId(runId);
        setIsStreaming(true);
        // Build SSE URL with auth token
        const token = useAuthStore.getState().accessToken;
        const streamUrl = agentRunStreamUrl(runId);
        const url = token
            ? `${streamUrl}?token=${encodeURIComponent(token)}`
            : streamUrl;
        const es = new EventSource(url);
        eventSourceRef.current = es;
        let streamClosed = false;
        const closeStream = (status, data) => {
            if (streamClosed)
                return;
            streamClosed = true;
            es.close();
            eventSourceRef.current = null;
            setIsStreaming(false);
            setCurrentRunId(null);
            setRuns((prev) => prev.map((r, i) => {
                if (i !== prev.length - 1)
                    return r;
                return {
                    ...r,
                    status,
                    output: data?.output != null
                        ? data.output?.response ??
                            JSON.stringify(data.output)
                        : r.output,
                    errorMessage: data?.error_message ?? r.errorMessage,
                    durationMs: data?.duration_ms ?? r.durationMs,
                    iterations: data?.iterations ?? r.iterations,
                };
            }));
        };
        es.addEventListener("llm_start", (e) => {
            const data = JSON.parse(e.data);
            updateCurrentRun((r) => ({
                ...r,
                steps: [
                    ...r.steps,
                    {
                        stepOrder: data.step_order,
                        type: "llm_call",
                        toolName: null,
                        input: null,
                        output: null,
                        tokenUsage: null,
                        durationMs: null,
                        status: "running",
                    },
                ],
            }));
        });
        es.addEventListener("llm_end", (e) => {
            const data = JSON.parse(e.data);
            updateCurrentRun((r) => {
                const steps = [...r.steps];
                const idx = steps.findLastIndex((s) => s.type === "llm_call" && s.status === "running");
                if (idx >= 0) {
                    steps[idx] = {
                        ...steps[idx],
                        output: data.output,
                        tokenUsage: data.token_usage,
                        durationMs: data.duration_ms,
                        status: "done",
                    };
                }
                const newTokens = data.token_usage?.total_tokens ?? null;
                return {
                    ...r,
                    steps,
                    totalTokens: newTokens != null
                        ? (r.totalTokens ?? 0) + newTokens
                        : r.totalTokens,
                };
            });
        });
        es.addEventListener("tool_start", (e) => {
            const data = JSON.parse(e.data);
            updateCurrentRun((r) => ({
                ...r,
                steps: [
                    ...r.steps,
                    {
                        stepOrder: data.step_order,
                        type: "tool_call",
                        toolName: data.tool_name,
                        input: data.input,
                        output: null,
                        tokenUsage: null,
                        durationMs: null,
                        status: "running",
                    },
                ],
            }));
        });
        es.addEventListener("tool_end", (e) => {
            const data = JSON.parse(e.data);
            updateCurrentRun((r) => {
                const steps = [...r.steps];
                const idx = steps.findLastIndex((s) => s.type === "tool_call" && s.status === "running");
                if (idx >= 0) {
                    steps[idx] = {
                        ...steps[idx],
                        output: data.output,
                        durationMs: data.duration_ms,
                        status: "done",
                    };
                }
                return { ...r, steps };
            });
        });
        es.addEventListener("tool_error", (e) => {
            const data = JSON.parse(e.data);
            updateCurrentRun((r) => {
                const steps = [...r.steps];
                const idx = steps.findLastIndex((s) => s.type === "tool_call" && s.status === "running");
                if (idx >= 0) {
                    steps[idx] = {
                        ...steps[idx],
                        type: "tool_error",
                        output: { error: data.error },
                        durationMs: data.duration_ms,
                        status: "done",
                    };
                }
                return { ...r, steps };
            });
        });
        es.addEventListener("run_completed", (e) => {
            const data = JSON.parse(e.data);
            closeStream("completed", data);
        });
        es.addEventListener("run_failed", (e) => {
            const data = JSON.parse(e.data);
            closeStream("failed", data);
        });
        es.addEventListener("run_cancelled", (e) => {
            const data = JSON.parse(e.data);
            closeStream("cancelled", data);
        });
        es.onerror = () => {
            es.close();
            // Fetch the run record — the backend may have stored a real error message.
            void getAgentRun(runId)
                .then((run) => {
                closeStream("failed", {
                    error_message: run.error_message ??
                        (run.status === "failed"
                            ? "Agent run failed (no details recorded)"
                            : "Connection lost"),
                    duration_ms: run.duration_ms,
                    iterations: run.iterations,
                });
            })
                .catch(() => {
                closeStream("failed", { error_message: "Connection lost — could not reach agent service" });
            });
        };
    }, [agentId, isStreaming, updateCurrentRun]);
    const cancelRun = useCallback(async () => {
        if (!currentRunId)
            return;
        try {
            await cancelAgentRun(currentRunId);
        }
        catch {
            // Cancellation is best-effort
        }
    }, [currentRunId]);
    // Cleanup on unmount
    useEffect(() => {
        return () => {
            eventSourceRef.current?.close();
        };
    }, []);
    return { runs, currentRunId, isStreaming, startRun, cancelRun };
}
