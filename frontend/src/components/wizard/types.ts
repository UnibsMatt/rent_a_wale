import type { ImageSpec, ResourceSpec } from "@/api/types";

/** Everything the wizard needs to build the final create-deployment payload. */
export interface WizardConfig {
  name: string;
  hostname?: string;
  resources: ResourceSpec;
  serviceCount: number;
  imageSpec?: ImageSpec;
  composeYaml?: string;
  templateId?: string;
}

export const CPU_OPTIONS = [0.5, 1, 2, 4, 6, 8] as const;
export const MEMORY_OPTIONS_MB = [256, 512, 1024, 2048, 4096, 8192, 16384] as const;
export const STORAGE_MIN_GB = 1;
export const STORAGE_MAX_GB = 100;
