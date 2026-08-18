import { AdminNav } from "@/components/layout/AdminNav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AdminNav />
      {children}
    </>
  );
}
