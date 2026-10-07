import { afterEach, describe, expect, it, vi } from "vitest";
import { api, resetAdminSessionForUnauthorized } from "../../packages/api-client/src/index";

const session = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "owner@example.test",
  permissions: ["catalog.read"],
  csrf_token: "csrf-for-this-session",
  expires_at: "2026-10-07T12:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
  resetAdminSessionForUnauthorized();
});

describe("admin API client", () => {
  it("logs in through the same-origin API and sends the session CSRF token only for logout", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(session), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.adminLogin({ email: "owner@example.test", password: "safe local test password" });
    await api.adminLogout();

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/admin/auth/login", expect.objectContaining({
      method: "POST", credentials: "include", cache: "no-store",
    }));
    const loginHeaders = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(loginHeaders.get("x-csrf-token")).toBeNull();
    expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify({ email: "owner@example.test", password: "safe local test password" }));

    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/admin/auth/logout", expect.objectContaining({ method: "POST", credentials: "include" }));
    const logoutHeaders = new Headers(fetchMock.mock.calls[1][1].headers);
    expect(logoutHeaders.get("x-csrf-token")).toBe(session.csrf_token);
  });

  it("forgets an expired admin CSRF token before the next mutation", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(session), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "SESSION_REQUIRED" }), { status: 401, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "SESSION_REQUIRED" }), { status: 401, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await api.adminSession();
    await expect(api.adminSession()).rejects.toMatchObject({ status: 401 });
    await expect(api.adminLogout()).rejects.toMatchObject({ status: 401 });

    expect(fetchMock.mock.calls[2][0]).toBe("/api/v1/admin/session");
  });
});
