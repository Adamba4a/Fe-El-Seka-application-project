"use client";

import type { AdminQueueItem } from "@fe-el-seka/shared";
import { useRouter } from "next/navigation";

interface SubmissionQueueProps {
  items: AdminQueueItem[];
}

export function SubmissionQueue({ items }: SubmissionQueueProps) {
  const router = useRouter();

  if (items.length === 0) return <p className="text-gray-400 text-sm py-8 text-center">No pending submissions</p>;

  return (
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr className="border-b text-left text-gray-500">
          <th className="pb-2 pr-4 font-medium">Name</th>
          <th className="pb-2 pr-4 font-medium">Phone</th>
          <th className="pb-2 pr-4 font-medium">Submitted</th>
          <th className="pb-2 font-medium">Attempt</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr
            key={item.submission_id}
            onClick={() => router.push(`/verification/${item.submission_id}`)}
            className="border-b hover:bg-gray-50 cursor-pointer"
          >
            <td className="py-3 pr-4">{item.user_name}</td>
            <td className="py-3 pr-4 text-gray-500">{item.phone_number}</td>
            <td className="py-3 pr-4 text-gray-500">{new Date(item.submitted_at).toLocaleString()}</td>
            <td className="py-3">
              <span className="px-2 py-0.5 bg-gray-100 rounded text-xs">{item.attempt_number}/3</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
