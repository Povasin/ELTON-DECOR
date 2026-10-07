export type GalleryMedia = {
  id: string;
  type: "image" | "video";
  url: string;
  alt_text: string;
  position: number;
};

export function sortGalleryMedia(media: GalleryMedia[]): GalleryMedia[] {
  return [...media].sort((left, right) => {
    // The storefront contract presents the first image as the hero media and
    // keeps video after every image, even when legacy rows have mixed positions.
    const typeOrder = (item: GalleryMedia) => item.type === "image" ? 0 : 1;
    return typeOrder(left) - typeOrder(right) || left.position - right.position || left.id.localeCompare(right.id);
  });
}

export function nextGalleryIndex(index: number, length: number): number {
  return length > 0 ? (index + 1) % length : 0;
}

export function previousGalleryIndex(index: number, length: number): number {
  return length > 0 ? (index - 1 + length) % length : 0;
}
