import { z } from 'zod';

const idSchema = z.uuid();

export const CodexCapabilityV1Schema = z.object({
  status: z.enum(['available', 'unavailable', 'needs_auth', 'unsupported']),
  reason: z.string(),
  codex_path: z.string().nullable(),
  codex_version: z.string().nullable(),
  app_server_available: z.boolean(),
  image_generation_advertised: z.boolean(),
  e2e_verified: z.boolean(),
  checked_at: z.string().min(1),
}).strict();

export const CodexRunV1Schema = z.object({
  run_id: idSchema,
  task_id: idSchema,
  panel_id: idSchema,
  status: z.enum(['queued', 'running', 'candidate_ready', 'failed']),
  candidate_id: idSchema.nullable(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  error_reason: z.string().nullable(),
  created_at: z.string().min(1),
}).strict().superRefine((run, context) => {
  const validShape = (
    run.status === 'queued'
      && run.started_at === null
      && run.completed_at === null
      && run.candidate_id === null
  ) || (
    run.status === 'running'
      && run.started_at !== null
      && run.completed_at === null
      && run.candidate_id === null
  ) || (
    run.status === 'candidate_ready'
      && run.started_at !== null
      && run.completed_at !== null
      && run.candidate_id !== null
  ) || (
    run.status === 'failed'
      && run.started_at !== null
      && run.completed_at !== null
      && run.candidate_id === null
  );
  if (!validShape) {
    context.addIssue({ code: 'custom', message: 'Codex run fields do not match its status' });
  }
});

export type CodexCapabilityV1 = z.infer<typeof CodexCapabilityV1Schema>;
export type CodexRunV1 = z.infer<typeof CodexRunV1Schema>;
