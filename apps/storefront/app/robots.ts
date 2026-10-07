import type { MetadataRoute } from "next";
import { absoluteSiteUrl } from "../lib/site";

export default function robots(): MetadataRoute.Robots {
  return { rules: [{ userAgent: "*", allow: "/", disallow: ["/admin", "/cart", "/checkout", "/result"] }], sitemap: absoluteSiteUrl("/sitemap.xml") };
}
