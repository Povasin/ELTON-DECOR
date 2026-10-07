const LOCAL_SITE_URL = "http://localhost:3000";

export function siteUrl(): URL {
  const configured = process.env.ELTON_SITE_URL?.trim();
  if (configured) {
    try {
      const url = new URL(configured);
      if (url.protocol === "http:" || url.protocol === "https:") return url;
    } catch {
      // Keep metadata generation safe when a deployment has a malformed value.
    }
  }
  return new URL(LOCAL_SITE_URL);
}

export function absoluteSiteUrl(path: string): string {
  return new URL(path, siteUrl()).toString();
}
