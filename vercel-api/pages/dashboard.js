import dynamic from "next/dynamic";

const DashboardContent = dynamic(() => import("../components/DashboardContent"), {
  ssr: false,
  loading: () => (
    <div style={{
      minHeight: "100vh", background: "#0A0C10", color: "#5C6479",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "ui-monospace, monospace", fontSize: 13,
    }}>
      불러오는 중...
    </div>
  ),
});

export default function DashboardPage() {
  return <DashboardContent />;
}
