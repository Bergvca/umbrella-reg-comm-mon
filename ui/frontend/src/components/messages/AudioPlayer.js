import { jsx as _jsx } from "react/jsx-runtime";
import { useQuery } from "@tanstack/react-query";
import { getAudioUrl } from "@/api/messages";
import { Skeleton } from "@/components/ui/skeleton";
export function AudioPlayer({ esIndex, docId }) {
    const { data, isLoading, isError } = useQuery({
        queryKey: ["audio", esIndex, docId],
        queryFn: () => getAudioUrl(esIndex, docId),
        staleTime: (result) => {
            const expiresIn = result.state.data?.expires_in;
            return expiresIn ? (expiresIn - 30) * 1000 : 5 * 60 * 1000;
        },
    });
    if (isLoading) {
        return _jsx(Skeleton, { className: "h-10 w-full" });
    }
    if (isError || !data?.url) {
        return (_jsx("p", { className: "text-sm text-muted-foreground italic", children: "Audio not available." }));
    }
    return (
    // eslint-disable-next-line jsx-a11y/media-has-caption
    _jsx("audio", { controls: true, className: "w-full", src: data.url, children: "Your browser does not support the audio element." }));
}
