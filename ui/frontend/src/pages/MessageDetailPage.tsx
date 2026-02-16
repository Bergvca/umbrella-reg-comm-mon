import { useParams, Link } from "react-router";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { MessageDisplay } from "@/components/messages/MessageDisplay";
import { LinkedAlerts } from "@/components/messages/LinkedAlerts";
import { useMessage } from "@/hooks/useMessages";

export function MessageDetailPage() {
  const { index, docId } = useParams<{ index: string; docId: string }>();
  const esIndex = index ?? "";
  const esDocId = docId ?? "";

  const { data: message, isLoading, isError } = useMessage(esIndex, esDocId);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !message) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center space-y-3">
            <p className="text-muted-foreground">Message not found.</p>
            <Link to="/messages" className="text-sm text-primary hover:underline">
              ← Back to Messages
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/messages">Messages</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{message.channel} / {esDocId}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <MessageDisplay message={message} esIndex={esIndex} />

      <Separator />

      <div className="space-y-3">
        <h2 className="text-base font-semibold">Linked Alerts</h2>
        <LinkedAlerts alerts={[]} />
      </div>
    </div>
  );
}
