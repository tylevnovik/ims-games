/** Base path for the site, without trailing slash. e.g. "/ims-games" or "" */
export const base: string = (import.meta.env.BASE_URL || "/").replace(/\/$/, "");

export function gameHref(gameId: string): string {
  return `${base}/games/detail?id=${encodeURIComponent(gameId)}`;
}

export function sourceHref(sourceId: string): string {
  return `${base}/sources/detail?id=${encodeURIComponent(sourceId)}`;
}
