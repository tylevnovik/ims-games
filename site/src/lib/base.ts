/** Base path for the site, without trailing slash. e.g. "/ims-games" or "" */
export const base: string = (import.meta.env.BASE_URL || "/").replace(/\/$/, "");
