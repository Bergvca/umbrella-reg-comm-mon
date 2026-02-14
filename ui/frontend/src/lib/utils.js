import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { ROLE_HIERARCHY } from "./constants";
/** shadcn/ui class merge helper */
export function cn(...inputs) {
    return twMerge(clsx(inputs));
}
/** Check if user has at least the given role level */
export function hasRole(userRoles, requiredRole) {
    const requiredLevel = ROLE_HIERARCHY[requiredRole] ?? 0;
    return userRoles.some((r) => (ROLE_HIERARCHY[r] ?? 0) >= requiredLevel);
}
/** Format ISO datetime for display */
export function formatDateTime(iso) {
    return new Date(iso).toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}
/** Format relative time (e.g., "2 hours ago") */
export function formatRelative(iso) {
    const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    const intervals = [
        [86400, "day"],
        [3600, "hour"],
        [60, "minute"],
    ];
    for (const [secs, label] of intervals) {
        const count = Math.floor(seconds / secs);
        if (count >= 1)
            return `${count} ${label}${count > 1 ? "s" : ""} ago`;
    }
    return "just now";
}
