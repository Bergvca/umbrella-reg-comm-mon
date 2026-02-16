import { useQuery } from "@tanstack/react-query";
import { getAudioUrl } from "@/api/messages";
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  esIndex: string;
  docId: string;
}

export function AudioPlayer({ esIndex, docId }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["audio", esIndex, docId],
    queryFn: () => getAudioUrl(esIndex, docId),
    staleTime: (result) => {
      const expiresIn = result.state.data?.expires_in;
      return expiresIn ? (expiresIn - 30) * 1000 : 5 * 60 * 1000;
    },
  });

  if (isLoading) {
    return <Skeleton className="h-10 w-full" />;
  }

  if (isError || !data?.url) {
    return (
      <p className="text-sm text-muted-foreground italic">Audio not available.</p>
    );
  }

  return (
    // eslint-disable-next-line jsx-a11y/media-has-caption
    <audio controls className="w-full" src={data.url}>
      Your browser does not support the audio element.
    </audio>
  );
}
