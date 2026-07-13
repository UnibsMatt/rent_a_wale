import axios from "axios";
import type { ApiErrorEnvelope } from "@/api/types";

/**
 * Extract a human-readable message from any error.
 * All API errors follow the envelope: { error: { code, message, detail? } }.
 */
export function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as Partial<ApiErrorEnvelope> | undefined;
    if (data?.error?.message) return data.error.message;
    const status = err.response?.status;
    if (status === 402) return "Insufficient credits. Top up your balance to continue.";
    if (status === 429) return "You are being rate limited. Please slow down and try again.";
    if (status === 401) return "Your session has expired. Please sign in again.";
    if (!err.response) return "Network error — could not reach the server.";
    return err.message || "Request failed";
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}

export function getErrorCode(err: unknown): string | null {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as Partial<ApiErrorEnvelope> | undefined;
    return data?.error?.code ?? null;
  }
  return null;
}
