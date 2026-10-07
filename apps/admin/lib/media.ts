export type AdminMediaLike = {
  id: string;
  type: "image" | "video";
  url: string;
  alt_text: string;
  position: number;
};

/** A draft holds all selected images and exactly one most recently selected video. */
export function stageAdminMedia<T extends { type: "image" | "video" }>(current: T[], selected: T[]): T[] {
  const combined = [...current, ...selected];
  const latestVideo = [...combined].reverse().find((item) => item.type === "video");
  return combined.filter((item) => item.type === "image" || item === latestVideo);
}

export function hasAtMostOneVideo(
  saved: Array<{ id: string; type: "image" | "video" }>,
  removals: string[],
  additions: Array<{ type: "image" | "video" }>,
): boolean {
  const retainedVideos = saved.filter((item) => item.type === "video" && !removals.includes(item.id)).length;
  return retainedVideos + additions.filter((item) => item.type === "video").length <= 1;
}

export function sortAdminMedia<T extends AdminMediaLike>(media: T[]): T[] {
  return [...media].sort((left, right) => {
    const typeOrder = (item: AdminMediaLike) => item.type === "image" ? 0 : 1;
    return typeOrder(left) - typeOrder(right) || left.position - right.position || left.id.localeCompare(right.id);
  });
}

/** Apply the server's successful upload response to the visible editor state. */
export function appendAdminMedia<T extends AdminMediaLike>(current: T[] | undefined, uploaded: T): T[] {
  return sortAdminMedia([...((current ?? []).filter((media) => media.id !== uploaded.id)), uploaded]);
}

/** Apply the server's successful delete response to the visible editor state. */
export function removeAdminMedia<T extends AdminMediaLike>(current: T[] | undefined, mediaId: string): T[] {
  return (current ?? []).filter((media) => media.id !== mediaId);
}
