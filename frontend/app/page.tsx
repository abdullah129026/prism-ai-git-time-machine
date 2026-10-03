import Inspector from "@/components/Inspector";
import TimelineCanvas from "@/components/TimelineCanvas";
import TopBar from "@/components/TopBar";

/** Explorer shell: top bar, timeline canvas, commit inspector. */
export default function Home() {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-canvas text-ink">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <TimelineCanvas />
        <Inspector />
      </div>
    </div>
  );
}
