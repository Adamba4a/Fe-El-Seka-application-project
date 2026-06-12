import type { Ride } from "@fe-el-seka/shared";
import { Input } from "@fe-el-seka/ui";

const _placeholder: Ride = {
  id: "00000000-0000-0000-0000-000000000000",
  driverId: "00000000-0000-0000-0000-000000000000",
  origin: { lat: 30.0444, lng: 31.2357 },
  destination: { lat: 30.0626, lng: 31.2497 },
  departureAt: new Date().toISOString(),
  status: "active",
  createdAt: new Date().toISOString(),
};

export default function AdminHome() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-4xl font-bold">Fe El Seka Admin</h1>
      <Input placeholder="Search rides..." />
    </main>
  );
}
