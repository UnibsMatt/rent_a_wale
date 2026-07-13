import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/api/templates";
import { getErrorMessage } from "@/lib/errors";
import { toast } from "@/components/ui/toast";

export function useTemplates() {
  return useQuery({ queryKey: ["templates"], queryFn: templatesApi.list });
}

export function useSubmitTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: templatesApi.submit,
    onSuccess: () => {
      toast.success("Template submitted", "It will appear once an admin approves it.");
      queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (err) => toast.error("Submission failed", getErrorMessage(err)),
  });
}
