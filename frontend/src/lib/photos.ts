/**
 * Openly licensed place photos, self-hosted in /public/images/places (downloaded once from
 * Wikimedia Commons, resized to 1920 px; displayed cropped). Every entry carries what the licence
 * requires us to show: author, licence, link to the licence and to the source. See /credits.
 */

export interface PlacePhotoInfo {
  key: string;
  src: string;
  /** What the photo actually shows (used as alt text where the photo is not decorative). */
  place: string;
  author: string;
  license: string;
  licenseUrl: string;
  source: string;
}

const P = (
  key: string,
  place: string,
  author: string,
  license: string,
  licenseUrl: string,
  source: string,
  file = key,
): PlacePhotoInfo => ({
  key,
  src: `/images/places/${file}.jpg`,
  place,
  author,
  license,
  licenseUrl,
  source,
});

const BY_SA = "https://creativecommons.org/licenses/by-sa/4.0/";

export const PHOTOS: PlacePhotoInfo[] = [
  P("hero-islamic-civilization", "Center of Islamic Civilization, Tashkent", "Зинҳор Насрӣ", "CC BY-SA 4.0", BY_SA,
    "https://commons.wikimedia.org/wiki/File:Center_of_Islamic_Civilization_of_Uzbekistan_Tashkent_2026_001.jpg"),
  P("hero-registan-night", "Registan, Samarkand, at night", "Benjamin Goetzinger", "CC BY-SA 4.0", BY_SA,
    "https://commons.wikimedia.org/wiki/File:Registan_square_Samarkand,_Uzbekistan,_at_night.jpg"),
  P("samarkand", "Registan, Samarkand", "Ziegler175", "CC BY-SA 4.0", BY_SA,
    "https://commons.wikimedia.org/wiki/File:Memorial_complex_%22Registan%22_in_Samarkand_(0).jpg"),
  P("bukhara", "Kalyan Minaret at night, Bukhara", "Pouria Afkhami (Pixoos)", "CC BY-SA 4.0", BY_SA,
    "https://commons.wikimedia.org/wiki/File:Bukhara_by_Pouria_Afkhami_aka_pixoos_01.jpg", "bukhara-kalyan-night"),
  P("khiva", "Kalta Minor and Kukhna Ark, Khiva", "Adam Harangozó", "CC BY-SA 4.0", BY_SA,
    "https://commons.wikimedia.org/wiki/File:Kalta_Minor_and_Kukhna_Ark,_Khiva.jpg"),
  P("tashkent", "Tashkent City, Tashkent", "Solijonovm1996", "CC BY-SA 4.0", BY_SA,
    "https://commons.wikimedia.org/wiki/File:TashkentCity.jpg"),
  P("fergana", "Margilan, Fergana Valley", "Stephanieadams99", "CC BY-SA 4.0", BY_SA,
    "https://commons.wikimedia.org/wiki/File:Margilan_.jpg"),
  P("kokand", "Palace of Khudayar Khan, Kokand", "Petar Milošević", "CC BY-SA 4.0", BY_SA,
    "https://commons.wikimedia.org/wiki/File:Palace_of_Khud%C3%A1y%C3%A1r_Kh%C3%A1n,_Kokand_(%D0%94%D0%B2%D0%BE%D1%80%D0%B5%D1%86_%D0%A5%D1%83%D0%B4%D0%BE%D1%8F%D1%80-%D1%85%D0%B0%D0%BD%D0%B0,_Xudoyorxon_o%CA%BBrdasi).jpg"),
  P("termez", "Ruins of Ancient Termez", "Miss Kamola", "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/",
    "https://commons.wikimedia.org/wiki/File:Ruins_of_Ancient_Termez.jpg"),
  P("namangan", "Kurban Ata Jame Mosque, Norin, Namangan region", "Komilkhuja", "CC BY 4.0",
    "https://creativecommons.org/licenses/by/4.0/",
    "https://commons.wikimedia.org/wiki/File:Kurban_Ata_Jame%27_Mosque._Norin,_Namangan_2024.jpg"),
];

const BY_KEY = new Map(PHOTOS.map((p) => [p.key, p]));
/** Page-banner art and the neutral fallback for places T-Port has no photo of. */
export const HERO_PHOTO = BY_KEY.get("hero-registan-night")!;
/** The big photo at the top of the home page. */
export const HOME_HERO_PHOTO = BY_KEY.get("hero-islamic-civilization")!;

/**
 * Photo for a location or station id ("bukhara", "bukhara-rail"), or null when T-Port has no photo
 * of that place. Callers decide on a fallback; a photo is never labelled as a place it doesn't show.
 */
export function photoForPlace(id: string): PlacePhotoInfo | null {
  return BY_KEY.get(id.split("-")[0]) ?? null;
}
