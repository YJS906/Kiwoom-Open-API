import { ExternalLink, Newspaper } from "lucide-react";

import { formatDateTime } from "@/lib/format";
import type { NewsItem } from "@/types/dashboard";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function NewsPanel({
  items,
  provider,
  loading,
  companyName
}: {
  items: NewsItem[];
  provider: string | null;
  loading: boolean;
  companyName: string;
}) {
  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-border/80 px-5 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-text">실시간 뉴스</h2>
            <p className="mt-1 text-xs text-muted">{companyName || "선택 종목"} 관련 최신 기사</p>
          </div>
          {provider ? <Badge>{provider.toUpperCase()}</Badge> : null}
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="space-y-3 p-5">
            {Array.from({ length: 5 }).map((_, index) => (
              <Skeleton key={index} className="h-24 w-full rounded-xl" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <Newspaper className="h-8 w-8 text-muted" />
            <p className="text-sm text-muted">표시할 뉴스가 없습니다.</p>
          </div>
        ) : (
          <ul className="divide-y divide-border/70">
            {items.map((item) => (
              <li key={`${item.url}-${item.published_at ?? ""}`} className="p-5 transition hover:bg-panelMuted/50">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block space-y-2"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-medium leading-6 text-text">{item.title}</p>
                    <ExternalLink className="mt-1 h-4 w-4 flex-none text-muted" />
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <span>{item.source}</span>
                    <span>•</span>
                    <span>{formatDateTime(item.published_at)}</span>
                  </div>
                  {item.summary ? (
                    <p className="line-clamp-3 text-sm leading-6 text-muted">{item.summary}</p>
                  ) : null}
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
