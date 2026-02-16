import { useQuery } from "@tanstack/react-query";
import { getRoles } from "@/api/roles";

export function useRoles() {
  return useQuery({
    queryKey: ["roles"],
    queryFn: getRoles,
    staleTime: 10 * 60 * 1000,
  });
}
