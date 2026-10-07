"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { trackEvent } from "@elton/analytics";

export default function AnalyticsPageView() {
  const pathname = usePathname();
  useEffect(() => { trackEvent({ name: "page_view", path: pathname }); }, [pathname]);
  return null;
}
