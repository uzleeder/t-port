/**
 * Turns a picked photo into a small square for upload: centre crop, at most 512 px, WebP (JPEG
 * where the browser can't encode WebP). Re-drawing on a canvas also drops camera metadata such as
 * location. The server checks the result again (format, size, dimensions).
 */

export const AVATAR_ACCEPT = "image/png,image/jpeg,image/webp";
const MAX_PICK_BYTES = 20 * 1024 * 1024;
const MAX_UPLOAD_BYTES = 1_000_000; // matches the API limit
const SIDE = 512;

export class AvatarError extends Error {}

function toBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, type, quality));
}

export async function prepareAvatar(file: File): Promise<Blob> {
  if (!file.type.startsWith("image/")) throw new AvatarError("Choose a photo (JPG, PNG or WebP).");
  if (file.size > MAX_PICK_BYTES) throw new AvatarError("That photo is over 20 MB. Choose a smaller one.");

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new AvatarError("Couldn't read that image. Try a JPG, PNG or WebP photo.");
  }
  const crop = Math.min(bitmap.width, bitmap.height);
  if (crop < 32) {
    bitmap.close();
    throw new AvatarError("That image is too small. Use one at least 32 pixels wide.");
  }
  const side = Math.min(SIDE, crop);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = side;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new AvatarError("Your browser couldn't process the photo.");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bitmap, (bitmap.width - crop) / 2, (bitmap.height - crop) / 2, crop, crop, 0, 0, side, side);
  bitmap.close();

  for (const quality of [0.86, 0.7]) {
    let blob = await toBlob(canvas, "image/webp", quality);
    if (!blob || blob.type !== "image/webp") blob = await toBlob(canvas, "image/jpeg", quality);
    if (blob && blob.size <= MAX_UPLOAD_BYTES) return blob;
  }
  throw new AvatarError("Couldn't make that photo small enough. Try another one.");
}
