import { Separator } from "@/components/ui/separator";
import { ParticipantList } from "./ParticipantList";
import { AudioPlayer } from "./AudioPlayer";
import { EnrichmentPanel } from "./EnrichmentPanel";
import { formatDateTime } from "@/lib/utils";
import type { ESMessage } from "@/lib/types";

interface Props {
  message: ESMessage;
  esIndex: string;
}

export function MessageDisplay({ message, esIndex }: Props) {
  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-muted-foreground">
        <span>
          Channel: <span className="text-foreground font-medium capitalize">{message.channel}</span>
        </span>
        {message.direction && (
          <span>
            Direction: <span className="text-foreground font-medium capitalize">{message.direction}</span>
          </span>
        )}
        <span>
          Timestamp: <span className="text-foreground">{formatDateTime(message.timestamp)}</span>
        </span>
      </div>

      <Separator />

      <div>
        <h4 className="font-medium mb-2">Participants</h4>
        <ParticipantList participants={message.participants} />
      </div>

      {(message.body_text ?? message.transcript ?? message.translated_text ?? message.audio_ref) && (
        <>
          <Separator />
          <div>
            <h4 className="font-medium mb-2">Content</h4>
            <div className="space-y-3">
              {message.body_text && (
                <div>
                  <p className="whitespace-pre-wrap">{message.body_text}</p>
                </div>
              )}
              {message.transcript && (
                <div>
                  <p className="text-muted-foreground text-xs uppercase tracking-wide mb-1">
                    Transcript
                  </p>
                  <p className="whitespace-pre-wrap">{message.transcript}</p>
                </div>
              )}
              {message.translated_text && (
                <div>
                  <p className="text-muted-foreground text-xs uppercase tracking-wide mb-1">
                    Translation {message.language ? `(from ${message.language})` : ""}
                  </p>
                  <p className="whitespace-pre-wrap">{message.translated_text}</p>
                </div>
              )}
              {message.audio_ref && (
                <div>
                  <p className="text-muted-foreground text-xs uppercase tracking-wide mb-1">
                    Audio
                  </p>
                  <AudioPlayer esIndex={esIndex} docId={message.message_id} />
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {message.attachments.length > 0 && (
        <>
          <Separator />
          <div>
            <h4 className="font-medium mb-2">
              Attachments ({message.attachments.length})
            </h4>
            <ul className="space-y-1">
              {message.attachments.map((a, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span className="font-medium">{a.name}</span>
                  <span className="text-muted-foreground text-xs">{a.content_type}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}

      <Separator />

      <div>
        <h4 className="font-medium mb-2">Enrichments</h4>
        <EnrichmentPanel message={message} />
      </div>
    </div>
  );
}
