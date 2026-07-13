import { useMemo, useState } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CheckCircle2, Plus, ShieldAlert, Trash2 } from "lucide-react";
import { z } from "zod";
import type { ComposeValidation, DeploymentKind, RestartPolicy } from "@/api/types";
import { deploymentsApi } from "@/api/deployments";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getErrorMessage } from "@/lib/errors";
import { formatMB } from "@/lib/format";
import {
  CPU_OPTIONS,
  MEMORY_OPTIONS_MB,
  STORAGE_MAX_GB,
  STORAGE_MIN_GB,
  type WizardConfig,
} from "@/components/wizard/types";

const HOSTNAME_RE = /^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$/;
const ENV_KEY_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const VOLUME_NAME_RE = /^[a-z0-9][a-z0-9_-]*$/;

const RESTART_POLICIES: RestartPolicy[] = ["unless-stopped", "always", "on-failure", "no"];

// ---------- Image form ----------

const imageSchema = z.object({
  name: z.string().min(2, "At least 2 characters").max(64),
  hostname: z
    .string()
    .max(40)
    .refine((v) => v === "" || HOSTNAME_RE.test(v), "Lowercase letters, digits and hyphens only")
    .optional(),
  image: z.string().min(1, "Image is required").max(256),
  command: z.string().max(1024).optional(),
  webPort: z
    .string()
    .refine(
      (v) => v === "" || (/^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 65535),
      "Port must be 1-65535",
    )
    .optional(),
  restartPolicy: z.enum(["no", "always", "on-failure", "unless-stopped"]),
  env: z.array(
    z.object({
      key: z.string().refine((v) => v === "" || ENV_KEY_RE.test(v), "Invalid variable name"),
      value: z.string().max(4096),
    }),
  ),
  volumes: z.array(
    z.object({
      name: z
        .string()
        .refine((v) => v === "" || VOLUME_NAME_RE.test(v), "Lowercase name"),
      containerPath: z
        .string()
        .refine((v) => v === "" || (v.startsWith("/") && !v.includes("..")), "Absolute path"),
    }),
  ),
  cpuCores: z.number(),
  memoryMb: z.number(),
  storageGb: z.number().min(0).max(STORAGE_MAX_GB),
});

type ImageFormValues = z.infer<typeof imageSchema>;

function ImageConfigForm({
  initial,
  onBack,
  onNext,
}: {
  initial: WizardConfig | null;
  onBack: () => void;
  onNext: (config: WizardConfig) => void;
}) {
  const form = useForm<ImageFormValues>({
    resolver: zodResolver(imageSchema),
    defaultValues: {
      name: initial?.name ?? "",
      hostname: initial?.hostname ?? "",
      image: initial?.imageSpec?.image ?? "",
      command: initial?.imageSpec?.command ?? "",
      webPort: initial?.imageSpec?.web_port ? String(initial.imageSpec.web_port) : "80",
      restartPolicy: initial?.imageSpec?.restart_policy ?? "unless-stopped",
      env: initial?.imageSpec
        ? Object.entries(initial.imageSpec.env).map(([key, value]) => ({ key, value }))
        : [],
      volumes:
        initial?.imageSpec?.volumes.map((v) => ({
          name: v.name,
          containerPath: v.container_path,
        })) ?? [],
      cpuCores: initial?.resources.cpu_cores ?? 1,
      memoryMb: initial?.resources.memory_mb ?? 1024,
      storageGb: initial?.resources.storage_gb ?? STORAGE_MIN_GB,
    },
  });
  const envArray = useFieldArray({ control: form.control, name: "env" });
  const volumesArray = useFieldArray({ control: form.control, name: "volumes" });
  const storageGb = form.watch("storageGb");

  function submit(values: ImageFormValues) {
    const env: Record<string, string> = {};
    for (const row of values.env) {
      if (row.key) env[row.key] = row.value;
    }
    onNext({
      name: values.name,
      hostname: values.hostname || undefined,
      resources: {
        cpu_cores: values.cpuCores,
        memory_mb: values.memoryMb,
        storage_gb: values.storageGb,
      },
      serviceCount: 1,
      imageSpec: {
        image: values.image.trim(),
        command: values.command?.trim() || undefined,
        env,
        web_port: values.webPort ? Number(values.webPort) : undefined,
        volumes: values.volumes
          .filter((v) => v.name && v.containerPath)
          .map((v) => ({ name: v.name, container_path: v.containerPath })),
        restart_policy: values.restartPolicy,
      },
    });
  }

  const err = form.formState.errors;

  return (
    <form onSubmit={form.handleSubmit(submit)} className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="wiz-name">Deployment name</Label>
          <Input id="wiz-name" placeholder="my-nginx" {...form.register("name")} />
          {err.name && <p className="text-xs text-red-500">{err.name.message}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wiz-hostname">Hostname (optional subdomain)</Label>
          <Input id="wiz-hostname" placeholder="auto-generated" {...form.register("hostname")} />
          {err.hostname && <p className="text-xs text-red-500">{err.hostname.message}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wiz-image">Docker image</Label>
          <Input id="wiz-image" placeholder="nginx:1.27" {...form.register("image")} />
          {err.image && <p className="text-xs text-red-500">{err.image.message}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wiz-port">Web port (public URL target)</Label>
          <Input id="wiz-port" placeholder="80" inputMode="numeric" {...form.register("webPort")} />
          {err.webPort && <p className="text-xs text-red-500">{err.webPort.message}</p>}
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="wiz-command">Command override (optional)</Label>
          <Input
            id="wiz-command"
            placeholder='e.g. nginx -g "daemon off;"'
            {...form.register("command")}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wiz-restart">Restart policy</Label>
          <Select id="wiz-restart" {...form.register("restartPolicy")}>
            {RESTART_POLICIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {/* Resources */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Resources</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="wiz-cpu">CPU cores</Label>
            <Select
              id="wiz-cpu"
              value={String(form.watch("cpuCores"))}
              onChange={(e) => form.setValue("cpuCores", Number(e.target.value))}
            >
              {CPU_OPTIONS.map((c) => (
                <option key={c} value={c}>
                  {c} {c === 1 ? "core" : "cores"}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wiz-mem">Memory</Label>
            <Select
              id="wiz-mem"
              value={String(form.watch("memoryMb"))}
              onChange={(e) => form.setValue("memoryMb", Number(e.target.value))}
            >
              {MEMORY_OPTIONS_MB.map((m) => (
                <option key={m} value={m}>
                  {formatMB(m)}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wiz-storage">
              Storage: <span className="font-semibold tabular-nums">{storageGb} GB</span>
            </Label>
            <Slider
              id="wiz-storage"
              min={STORAGE_MIN_GB}
              max={STORAGE_MAX_GB}
              step={1}
              value={storageGb}
              onChange={(e) => form.setValue("storageGb", Number(e.target.value))}
            />
          </div>
        </CardContent>
      </Card>

      {/* Env vars */}
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Environment variables</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => envArray.append({ key: "", value: "" })}
          >
            <Plus aria-hidden /> Add variable
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {envArray.fields.length === 0 && (
            <p className="text-sm text-muted-foreground">No environment variables.</p>
          )}
          {envArray.fields.map((field, i) => (
            <div key={field.id} className="flex items-start gap-2">
              <div className="flex-1">
                <Input
                  aria-label={`Variable ${i + 1} name`}
                  placeholder="KEY"
                  className="font-mono"
                  {...form.register(`env.${i}.key`)}
                />
                {err.env?.[i]?.key && (
                  <p className="mt-1 text-xs text-red-500">{err.env[i]?.key?.message}</p>
                )}
              </div>
              <div className="flex-[2]">
                <Input
                  aria-label={`Variable ${i + 1} value`}
                  placeholder="value"
                  className="font-mono"
                  {...form.register(`env.${i}.value`)}
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove variable ${i + 1}`}
                onClick={() => envArray.remove(i)}
              >
                <Trash2 aria-hidden />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Volumes */}
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Volumes</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => volumesArray.append({ name: "", containerPath: "" })}
          >
            <Plus aria-hidden /> Add volume
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {volumesArray.fields.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No persistent volumes (data is lost when the container is removed).
            </p>
          )}
          {volumesArray.fields.map((field, i) => (
            <div key={field.id} className="flex items-start gap-2">
              <div className="flex-1">
                <Input
                  aria-label={`Volume ${i + 1} name`}
                  placeholder="data"
                  className="font-mono"
                  {...form.register(`volumes.${i}.name`)}
                />
                {err.volumes?.[i]?.name && (
                  <p className="mt-1 text-xs text-red-500">{err.volumes[i]?.name?.message}</p>
                )}
              </div>
              <div className="flex-[2]">
                <Input
                  aria-label={`Volume ${i + 1} mount path`}
                  placeholder="/var/lib/data"
                  className="font-mono"
                  {...form.register(`volumes.${i}.containerPath`)}
                />
                {err.volumes?.[i]?.containerPath && (
                  <p className="mt-1 text-xs text-red-500">
                    {err.volumes[i]?.containerPath?.message}
                  </p>
                )}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove volume ${i + 1}`}
                onClick={() => volumesArray.remove(i)}
              >
                <Trash2 aria-hidden />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          <ArrowLeft aria-hidden /> Back
        </Button>
        <Button type="submit">
          Continue <ArrowRight aria-hidden />
        </Button>
      </div>
    </form>
  );
}

// ---------- Compose form ----------

function ComposeConfigForm({
  initial,
  onBack,
  onNext,
}: {
  initial: WizardConfig | null;
  onBack: () => void;
  onNext: (config: WizardConfig) => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [hostname, setHostname] = useState(initial?.hostname ?? "");
  const [storageGb, setStorageGb] = useState(initial?.resources.storage_gb ?? STORAGE_MIN_GB);
  const [yaml, setYaml] = useState(initial?.composeYaml ?? "");
  const [validation, setValidation] = useState<ComposeValidation | null>(null);
  const [touchedSinceValidate, setTouchedSinceValidate] = useState(false);

  const validateMutation = useMutation({
    mutationFn: (composeYaml: string) => deploymentsApi.validateCompose(composeYaml),
    onSuccess: (result) => {
      setValidation(result);
      setTouchedSinceValidate(false);
    },
  });

  const nameValid = name.trim().length >= 2;
  const hostnameValid = hostname === "" || HOSTNAME_RE.test(hostname);
  const canContinue =
    nameValid && hostnameValid && validation?.valid === true && !touchedSinceValidate;

  const aggregate = validation?.aggregate ?? null;
  const detected = validation?.services ?? [];

  const totalMemory = useMemo(
    () => detected.reduce((acc, s) => acc + s.memory_mb, 0),
    [detected],
  );
  const totalCpu = useMemo(
    () => detected.reduce((acc, s) => acc + Number(s.cpu_cores), 0),
    [detected],
  );

  function handleNext() {
    if (!validation?.valid) return;
    onNext({
      name: name.trim(),
      hostname: hostname || undefined,
      resources: {
        cpu_cores: aggregate ? Number(aggregate.cpu_cores) : totalCpu,
        memory_mb: aggregate?.memory_mb ?? totalMemory,
        storage_gb: storageGb,
      },
      serviceCount: Math.max(1, detected.length),
      composeYaml: yaml,
      templateId: initial?.templateId,
    });
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="cw-name">Deployment name</Label>
          <Input
            id="cw-name"
            placeholder="my-stack"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          {!nameValid && name !== "" && (
            <p className="text-xs text-red-500">At least 2 characters</p>
          )}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cw-hostname">Hostname (optional)</Label>
          <Input
            id="cw-hostname"
            placeholder="auto-generated"
            value={hostname}
            onChange={(e) => setHostname(e.target.value)}
          />
          {!hostnameValid && (
            <p className="text-xs text-red-500">Lowercase letters, digits, hyphens</p>
          )}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cw-storage">
            Storage: <span className="font-semibold tabular-nums">{storageGb} GB</span>
          </Label>
          <Slider
            id="cw-storage"
            min={STORAGE_MIN_GB}
            max={STORAGE_MAX_GB}
            step={1}
            value={storageGb}
            onChange={(e) => setStorageGb(Number(e.target.value))}
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="cw-yaml">docker-compose.yml</Label>
        <Textarea
          id="cw-yaml"
          value={yaml}
          onChange={(e) => {
            setYaml(e.target.value);
            setTouchedSinceValidate(true);
          }}
          spellCheck={false}
          className="min-h-[280px] font-mono text-xs leading-relaxed"
          placeholder={"services:\n  web:\n    image: nginx:1.27\n    ports:\n      - \"80\"\n"}
        />
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Named volumes only · no privileged mode, host network or bind mounts.
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => validateMutation.mutate(yaml)}
            loading={validateMutation.isPending}
            disabled={yaml.trim() === ""}
          >
            Validate
          </Button>
        </div>
      </div>

      {validateMutation.isError && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm">
          {getErrorMessage(validateMutation.error)}
        </div>
      )}

      {validation && !touchedSinceValidate && (
        <div className="space-y-4">
          {validation.errors.length > 0 && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4">
              <p className="mb-2 flex items-center gap-2 text-sm font-medium">
                <ShieldAlert className="h-4 w-4 text-red-500" aria-hidden />
                Validation failed
              </p>
              <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                {validation.errors.map((error, i) => (
                  <li key={i}>{error}</li>
                ))}
              </ul>
            </div>
          )}

          {validation.valid && (
            <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-hidden />
              Compose file is valid — {detected.length} service
              {detected.length === 1 ? "" : "s"} detected, {totalCpu} CPU /{" "}
              {formatMB(totalMemory)} total.
            </div>
          )}

          {detected.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Detected services</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Service</TableHead>
                      <TableHead>Image</TableHead>
                      <TableHead>Web port</TableHead>
                      <TableHead>CPU</TableHead>
                      <TableHead>Memory</TableHead>
                      <TableHead>Depends on</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {detected.map((s) => (
                      <TableRow key={s.name}>
                        <TableCell className="font-medium">{s.name}</TableCell>
                        <TableCell className="font-mono text-xs">{s.image}</TableCell>
                        <TableCell>{s.web_port ?? "—"}</TableCell>
                        <TableCell>{s.cpu_cores}</TableCell>
                        <TableCell>{formatMB(s.memory_mb)}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {s.depends_on.length ? s.depends_on.join(", ") : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      <div className="flex justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          <ArrowLeft aria-hidden /> Back
        </Button>
        <Button type="button" onClick={handleNext} disabled={!canContinue}>
          Continue <ArrowRight aria-hidden />
        </Button>
      </div>
    </div>
  );
}

export function ConfigStep({
  kind,
  initial,
  onBack,
  onNext,
}: {
  kind: DeploymentKind;
  initial: WizardConfig | null;
  onBack: () => void;
  onNext: (config: WizardConfig) => void;
}) {
  return kind === "image" ? (
    <ImageConfigForm initial={initial} onBack={onBack} onNext={onNext} />
  ) : (
    <ComposeConfigForm initial={initial} onBack={onBack} onNext={onNext} />
  );
}
