import { useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import type { CreateDeploymentRequest, DeploymentKind } from "@/api/types";
import { StepIndicator } from "@/components/wizard/step-indicator";
import { TypeStep } from "@/components/wizard/type-step";
import { ConfigStep } from "@/components/wizard/config-step";
import { EstimateStep } from "@/components/wizard/estimate-step";
import { LaunchStep } from "@/components/wizard/launch-step";
import type { WizardConfig } from "@/components/wizard/types";

/** Passed via router state when deploying an approved template. */
interface TemplatePrefill {
  template?: {
    id: string;
    name: string;
    composeYaml: string;
  };
}

export function DeploymentWizardPage() {
  const location = useLocation();
  const prefill = (location.state as TemplatePrefill | null)?.template;

  const initialConfig: WizardConfig | null = useMemo(
    () =>
      prefill
        ? {
            name: prefill.name,
            resources: { cpu_cores: 1, memory_mb: 1024, storage_gb: 1 },
            serviceCount: 1,
            composeYaml: prefill.composeYaml,
            templateId: prefill.id,
          }
        : null,
    [prefill],
  );

  const [step, setStep] = useState(prefill ? 2 : 1);
  const [kind, setKind] = useState<DeploymentKind | null>(prefill ? "compose" : null);
  const [config, setConfig] = useState<WizardConfig | null>(initialConfig);

  const request: CreateDeploymentRequest | null =
    kind !== null && config !== null
      ? {
          name: config.name,
          kind,
          resources: config.resources,
          hostname: config.hostname,
          image_spec: kind === "image" ? config.imageSpec : undefined,
          compose_yaml: kind === "compose" ? config.composeYaml : undefined,
          template_id: config.templateId,
        }
      : null;

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">New deployment</h1>
        <p className="text-sm text-muted-foreground">
          Launch a container or a compose stack with a public URL.
        </p>
      </div>

      <StepIndicator current={step} />

      {step === 1 && (
        <TypeStep value={kind} onChange={setKind} onNext={() => setStep(2)} />
      )}

      {step === 2 && kind !== null && (
        <ConfigStep
          kind={kind}
          initial={config}
          onBack={() => setStep(1)}
          onNext={(next) => {
            setConfig(next);
            setStep(3);
          }}
        />
      )}

      {step === 3 && kind !== null && config !== null && (
        <EstimateStep
          kind={kind}
          config={config}
          onBack={() => setStep(2)}
          onDeploy={() => setStep(4)}
        />
      )}

      {step === 4 && request !== null && <LaunchStep request={request} />}
    </div>
  );
}
