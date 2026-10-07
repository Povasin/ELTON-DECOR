"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@elton/api-client";

export function AdminControls() {
  const [signedIn, setSignedIn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    let mounted = true;
    void api.adminSession().then(
      () => { if (mounted) setSignedIn(true); },
      () => { if (mounted) setSignedIn(false); },
    );
    return () => { mounted = false; };
  }, [pathname]);

  async function logout() {
    setBusy(true);
    setFailed(false);
    try {
      await api.adminLogout();
      setSignedIn(false);
      router.replace("/login");
      router.refresh();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  if (!signedIn) return <Link href="/login">Вход</Link>;
  return <span className="admin-controls"><button type="button" className="link-button" onClick={() => void logout()} disabled={busy}>{busy ? "Выходим…" : "Выйти"}</button>{failed && <span role="status">Не удалось завершить сеанс.</span>}</span>;
}
