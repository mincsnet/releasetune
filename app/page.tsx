import { redirect } from "next/navigation";
import { getTodayMmdd } from "@/lib/tracks";

export default function HomePage() {
  const today = getTodayMmdd();
  redirect(`/date/${today}`);
}
