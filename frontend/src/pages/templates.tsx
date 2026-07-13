import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { FileCode2, Plus, Rocket } from "lucide-react";
import { z } from "zod";
import type { Template } from "@/api/types";
import { useSubmitTemplate, useTemplates } from "@/hooks/use-templates";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/states";
import { formatDate } from "@/lib/format";

const submitSchema = z.object({
  name: z.string().min(2, "At least 2 characters").max(128),
  description: z.string().max(2048),
  composeYaml: z.string().min(1, "Compose YAML is required").max(65_536),
});

type SubmitValues = z.infer<typeof submitSchema>;

function SubmitTemplateDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const submitMutation = useSubmitTemplate();
  const form = useForm<SubmitValues>({
    resolver: zodResolver(submitSchema),
    defaultValues: { name: "", description: "", composeYaml: "" },
  });
  const err = form.formState.errors;

  function onSubmit(values: SubmitValues) {
    submitMutation.mutate(
      {
        name: values.name,
        description: values.description,
        compose_yaml: values.composeYaml,
      },
      {
        onSuccess: () => {
          form.reset();
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Submit a template</DialogTitle>
          <DialogDescription>
            Share a compose stack with everyone. An admin reviews it before it becomes
            public.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="tpl-name">Name</Label>
            <Input id="tpl-name" placeholder="WordPress + MySQL" {...form.register("name")} />
            {err.name && <p className="text-xs text-red-500">{err.name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="tpl-desc">Description</Label>
            <Input
              id="tpl-desc"
              placeholder="What does this stack do?"
              {...form.register("description")}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="tpl-yaml">docker-compose.yml</Label>
            <Textarea
              id="tpl-yaml"
              spellCheck={false}
              className="min-h-[220px] font-mono text-xs"
              {...form.register("composeYaml")}
            />
            {err.composeYaml && (
              <p className="text-xs text-red-500">{err.composeYaml.message}</p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={submitMutation.isPending}>
              Submit for review
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TemplateCard({ template }: { template: Template }) {
  const navigate = useNavigate();
  return (
    <Card className="flex flex-col">
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div className="flex items-center gap-2">
          <FileCode2 className="h-5 w-5 text-primary" aria-hidden />
          <CardTitle className="text-base">{template.name}</CardTitle>
        </div>
        <span className="text-xs text-muted-foreground">{formatDate(template.created_at)}</span>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <p className="flex-1 text-sm text-muted-foreground">
          {template.description || "No description provided."}
        </p>
        <pre className="max-h-32 overflow-hidden rounded-md bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
          {template.compose_yaml}
        </pre>
        <Button
          onClick={() =>
            navigate("/deployments/new", {
              state: {
                template: {
                  id: template.id,
                  name: template.name,
                  composeYaml: template.compose_yaml,
                },
              },
            })
          }
        >
          <Rocket aria-hidden /> Deploy this stack
        </Button>
      </CardContent>
    </Card>
  );
}

export function TemplatesPage() {
  const templatesQuery = useTemplates();
  const [submitOpen, setSubmitOpen] = useState(false);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Templates</h1>
          <p className="text-sm text-muted-foreground">
            Approved compose stacks, ready to deploy in one click.
          </p>
        </div>
        <Button onClick={() => setSubmitOpen(true)}>
          <Plus aria-hidden /> Submit template
        </Button>
      </div>

      {templatesQuery.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : templatesQuery.isError ? (
        <ErrorState error={templatesQuery.error} onRetry={() => templatesQuery.refetch()} />
      ) : (templatesQuery.data ?? []).length === 0 ? (
        <EmptyState
          icon={<FileCode2 className="h-8 w-8" />}
          title="No templates yet"
          description="Be the first to share a compose stack with the community."
          action={
            <Button size="sm" onClick={() => setSubmitOpen(true)}>
              <Plus aria-hidden /> Submit template
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {templatesQuery.data?.map((t) => <TemplateCard key={t.id} template={t} />)}
        </div>
      )}

      <SubmitTemplateDialog open={submitOpen} onOpenChange={setSubmitOpen} />
    </div>
  );
}
