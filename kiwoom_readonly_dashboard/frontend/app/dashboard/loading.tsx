import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardLoading() {
  return (
    <main className="min-h-screen p-6">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6">
        <div className="grid grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-28 rounded-2xl" />
          ))}
        </div>
        <div className="grid grid-cols-[300px_minmax(0,1fr)_360px] gap-6">
          <Skeleton className="h-[820px] rounded-2xl" />
          <Skeleton className="h-[820px] rounded-2xl" />
          <Skeleton className="h-[820px] rounded-2xl" />
        </div>
      </div>
    </main>
  );
}
