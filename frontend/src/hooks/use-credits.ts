import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { creditsApi } from "@/api/credits";
import { getErrorMessage } from "@/lib/errors";
import { toast } from "@/components/ui/toast";

export function useBalance(options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: ["balance"],
    queryFn: creditsApi.balance,
    refetchInterval: options?.refetchInterval,
  });
}

export function useTransactions(page: number, pageSize = 20) {
  return useQuery({
    queryKey: ["transactions", page, pageSize],
    queryFn: () => creditsApi.transactions(page, pageSize),
    placeholderData: (prev) => prev,
  });
}

export function usePricing() {
  return useQuery({ queryKey: ["pricing"], queryFn: creditsApi.pricing });
}

export function usePurchaseCredits() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (amount: number) => creditsApi.purchase(amount),
    onSuccess: (tx) => {
      toast.success("Credits purchased", `New balance: ${tx.balance_after}`);
      queryClient.invalidateQueries({ queryKey: ["balance"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
    onError: (err) => toast.error("Purchase failed", getErrorMessage(err)),
  });
}
