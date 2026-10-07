"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ApiError, api } from "@elton/api-client";
import { Card, Notice } from "@elton/ui";

type AccessState = "checking" | "granted" | "unavailable";

export function AdminAccess({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AccessState>("checking");
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let mounted = true;
    void api.adminSession().then(
      () => { if (mounted) setState("granted"); },
      (error: unknown) => {
        if (!mounted) return;
        if (error instanceof ApiError && error.status === 401) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
          return;
        }
        setState("unavailable");
      },
    );
    return () => { mounted = false; };
  }, [pathname, router]);

  if (state === "checking") return <Card><p className="muted" role="status">Проверяем защищённую сессию…</p></Card>;
  if (state === "unavailable") return <Card><Notice tone="warning">Админка временно недоступна. Повторите попытку позже.</Notice></Card>;
  return <>{children}</>;
}
