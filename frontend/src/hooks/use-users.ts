import { useMutation, useQuery } from "@tanstack/react-query";
import { usersApi } from "@/api/users";
import { getErrorMessage } from "@/lib/errors";
import { toast } from "@/components/ui/toast";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: usersApi.me, staleTime: 60_000 });
}

export function useQuota() {
  return useQuery({ queryKey: ["quota"], queryFn: usersApi.quota });
}

export function useSessions() {
  return useQuery({ queryKey: ["sessions"], queryFn: usersApi.sessions });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: ({ current, next }: { current: string; next: string }) =>
      usersApi.changePassword(current, next),
    onSuccess: () => toast.success("Password changed"),
    onError: (err) => toast.error("Could not change password", getErrorMessage(err)),
  });
}
