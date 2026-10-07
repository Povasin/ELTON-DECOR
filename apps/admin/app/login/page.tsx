"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, api } from "@elton/api-client";
import { Card, Notice } from "@elton/ui";

function safeNext(value: string | null): "/products" | "/drafts" {
  return value === "/drafts" ? "/drafts" : "/products";
}

function loginError(error: unknown): string {
  if (error instanceof ApiError && error.status === 429) return "Слишком много попыток. Подождите минуту и попробуйте снова.";
  return "Не удалось войти. Проверьте email и пароль или повторите попытку позже.";
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNext(searchParams.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let mounted = true;
    void api.adminSession().then(
      () => { if (mounted) router.replace(next); },
      () => undefined,
    );
    return () => { mounted = false; };
  }, [next, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      await api.adminLogin({ email, password });
      router.replace(next);
      router.refresh();
    } catch (error) {
      setMessage(loginError(error));
    } finally {
      setBusy(false);
    }
  }

  return <><p className="muted">Elton Decor · backoffice</p><h1>Вход администратора</h1><Card><p>Используйте учётную запись владельца, созданную защищённой локальной процедурой bootstrap.</p><form className="login-form" onSubmit={(event) => void submit(event)}><label htmlFor="admin-email">Email<input id="admin-email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={254} /></label><label htmlFor="admin-password">Пароль<input id="admin-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required maxLength={128} /></label><button className="button" type="submit" disabled={busy}>{busy ? "Входим…" : "Войти"}</button></form>{message && <Notice tone="warning"><span role="alert">{message}</span></Notice>}</Card></>;
}

export default function LoginPage() {
  return <Suspense fallback={<Card><p className="muted">Открываем форму входа…</p></Card>}><LoginForm /></Suspense>;
}
