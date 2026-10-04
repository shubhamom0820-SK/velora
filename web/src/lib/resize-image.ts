/**
 * A photo made ready to upload (T-4.6): drawn on a canvas at most 2000 px on
 * its longest side and sent as a JPEG, to save the person's data. The server
 * re-encodes every photo anyway (T-4.4), at 1600 px.
 *
 * Every photo the browser can read goes through the canvas, small ones too, so
 * every upload is the same kind of file whatever the camera wrote: the canvas
 * also drops the file's EXIF, though the server's re-encode is what's relied on
 * for that (CLAUDE.md rule 15). A file the browser can't read goes up as it is,
 * and the API's answer says whether it's a photo we take (D-089): the server
 * decides, never this file (D-082).
 */

/** The longest side sent, in pixels. */
export const MAX_SIDE_PX = 2000;
/** JPEG quality for the canvas: the server's own re-encode follows. */
export const JPEG_QUALITY = 0.9;

export type Size = { width: number; height: number };

/** `size` scaled to fit within `max` on its longest side, never enlarged. */
export function fitWithin({ width, height }: Size, max: number): Size {
  const longest = Math.max(width, height);
  if (longest <= max) return { width, height };
  const scale = max / longest;
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

/**
 * The colour behind a transparent PNG once it's a JPEG: the surface token,
 * read from the page (tokens.css), so no colour lives here. Without it, a
 * canvas exports transparency as black.
 */
function surfaceColour(): string {
  return getComputedStyle(document.documentElement)
    .getPropertyValue("--surface")
    .trim();
}

/** The file decoded as an image, or null if this browser can't read it. */
async function decode(file: Blob): Promise<HTMLImageElement | null> {
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    // Drawn as displayed: browsers apply the EXIF orientation when drawing.
    await image.decode();
    return image;
  } catch {
    return null;
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** `file` as a JPEG within `max` px, or null when the browser can't read it. */
export async function resizeForUpload(
  file: Blob,
  max: number = MAX_SIDE_PX,
): Promise<Blob | null> {
  const image = await decode(file);
  if (!image || image.naturalWidth === 0 || image.naturalHeight === 0) {
    return null;
  }
  const { width, height } = fitWithin(
    { width: image.naturalWidth, height: image.naturalHeight },
    max,
  );
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) return null;
  const surface = surfaceColour();
  if (surface) {
    context.fillStyle = surface;
    context.fillRect(0, 0, width, height);
  }
  context.drawImage(image, 0, 0, width, height);
  return new Promise((resolve) => {
    canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY);
  });
}
