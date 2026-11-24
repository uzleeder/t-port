import Image from "next/image";
import { HERO_PHOTO, photoForPlace, type PlacePhotoInfo } from "@/lib/photos";

/**
 * A real photo of a place, filling its (relatively positioned) parent. With no photo for that
 * place it shows the Registan night photo as a neutral backdrop, marked decorative so it is never
 * announced as the wrong city.
 */
export function PlacePhoto({
  id,
  photo,
  sizes,
  className = "",
  eager = false,
  decorative = false,
}: {
  /** Location or station id; ignored when `photo` is given. */
  id?: string;
  photo?: PlacePhotoInfo;
  /** Rendered width hint for responsive loading, e.g. "(min-width: 1024px) 25vw, 80vw". */
  sizes: string;
  className?: string;
  /** Above-the-fold images: load immediately with high priority. */
  eager?: boolean;
  /** Purely decorative next to text that already names the place. */
  decorative?: boolean;
}) {
  const own = photo ?? (id ? photoForPlace(id) : null);
  const p = own ?? HERO_PHOTO;
  const alt = decorative || !own ? "" : p.place;
  return (
    <Image
      src={p.src}
      alt={alt}
      fill
      sizes={sizes}
      loading={eager ? "eager" : "lazy"}
      fetchPriority={eager ? "high" : "auto"}
      className={`object-cover ${className}`}
    />
  );
}
