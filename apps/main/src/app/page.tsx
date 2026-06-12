import type { User } from "@fe-el-seka/shared";
import { Button } from "@fe-el-seka/ui";

const _placeholder: User = {
  id: "00000000-0000-0000-0000-000000000000",
  phone: "+20100000000",
  role: "passenger",
  createdAt: new Date().toISOString(),
};

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-4xl font-bold">Fe El Seka</h1>
      <Button>Get Started</Button>
    </main>
  );
}
