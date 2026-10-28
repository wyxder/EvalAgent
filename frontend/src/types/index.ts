export interface LLMConfig {
  id: number;
  name: string;
  provider: string;
  api_base_url: string;
  api_key_masked: string;
  model_name: string;
  temperature: number;
  max_tokens: number;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface LLMConfigCreate {
  name: string;
  provider?: string;
  api_base_url: string;
  api_key: string;
  model_name: string;
  temperature?: number;
  max_tokens?: number;
  is_default?: boolean;
}

export interface LLMTestResult {
  success: boolean;
  message: string;
  latency_ms?: number;
}

export interface FieldDefinition {
  name: string;
  type: string;
  required: boolean;
  description: string;
}

export interface Dataset {
  id: number;
  name: string;
  description: string;
  sample_type: string;
  field_schema: FieldDefinition[];
  row_count: number;
  created_at: string;
  updated_at: string;
}

export interface DatasetRow {
  id: number;
  dataset_id: number;
  row_index: number;
  data: Record<string, any>;
  created_at: string;
}

export interface MetricDefinition {
  id: number;
  name: string;
  display_name: string;
  metric_type: string;
  config: Record<string, any>;
  category: string;
  is_builtin: boolean;
  created_at: string;
}

export interface EndpointTarget {
  id: number;
  name: string;
  description?: string | null;
  endpoint_url: string;
  transport_mode: 'json' | 'sse';
  authorization?: string | null;
  authorization_masked?: string;
  extra_headers?: string | null;
  request_body_template?: string | null;
  response_mapping?: Record<string, any> | null;
  default_test_input?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface ScenarioMetric {
  id: number;
  metric_definition_id: number;
  weight: number;
  pass_threshold: number | null;
  prompt_override?: string | null;
  metric_definition?: MetricDefinition;
}

export interface EvalScenario {
  id: number;
  name: string;
  description: string;
  scene_type: string;
  sample_type: string;
  is_preset: boolean;
  metrics: ScenarioMetric[];
  created_at: string;
}

export interface EvalTask {
  id: number;
  name: string;
  dataset_id: number;
  scenario_id: number;
  llm_config_id: number;
  status: string;
  progress: number;
  total_rows: number;
  completed_rows: number;
  error_message: string | null;
  summary_scores: Record<string, any> | null;
  scenario_snapshot?: Record<string, any> | null;
  evaluation_mode?: 'offline' | 'endpoint';
  endpoint_target_id?: number | null;
  target_config?: Record<string, any> | null;
  response_mapping?: Record<string, any> | null;
  result_save_mode?: 'task_only' | 'write_back';
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  dataset?: Dataset;
  scenario?: EvalScenario;
  llm_config?: LLMConfig;
}

export interface EvalRowResult {
  id: number;
  eval_task_id: number;
  row_index: number;
  metric_scores: Record<string, { score: number | null; reason: string }>;
  endpoint_trace?: Record<string, any> | null;
  is_pass: boolean | null;
  execution_time_ms: number | null;
  error: string | null;
  manual_status?: 'pass' | 'fail' | 'needs_fix' | 'needs_review' | null;
  manual_score?: number | null;
  manual_tags?: string[] | null;
  manual_note?: string | null;
  reviewed_at?: string | null;
  dataset_row?: DatasetRow;
  created_at: string;
}

export interface ReportSummary {
  eval_task: EvalTask;
  total_count: number;
  pass_count: number;
  fail_count: number;
  error_count: number;
  pass_rate: number;
  metric_summary: Record<string, { mean: number; min: number; max: number; pass_rate: number }>;
  manual_review_summary?: Record<string, number>;
}

export interface ReportListItem {
  eval_id: number;
  task_name: string;
  dataset_id: number;
  dataset_name?: string | null;
  scenario_id: number;
  scenario_name?: string | null;
  evaluation_mode?: 'offline' | 'endpoint';
  endpoint_target_id?: number | null;
  endpoint_name?: string | null;
  status: string;
  total_count: number;
  pass_count: number;
  fail_count: number;
  error_count: number;
  pass_rate: number;
  progress: number;
  completed_rows: number;
  total_rows?: number | null;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ReportListResponse {
  total: number;
  page: number;
  page_size: number;
  items: ReportListItem[];
}

export interface ReportCompareMetricDelta {
  metric: string;
  current_mean: number | null;
  baseline_mean: number | null;
  mean_delta: number | null;
  current_pass_rate: number | null;
  baseline_pass_rate: number | null;
  pass_rate_delta: number | null;
  current_error_count: number;
  baseline_error_count: number;
}

export interface ReportCompareRowItem {
  dataset_row_id: number;
  row_index: number;
  current_result_id?: number | null;
  baseline_result_id?: number | null;
  current_status?: string | null;
  baseline_status?: string | null;
  metric_deltas: Record<string, {
    current_score: number | string | null;
    baseline_score: number | string | null;
    delta: number | null;
  }>;
  dataset_row?: DatasetRow | null;
}

export interface ReportCompareResponse {
  current_eval: EvalTask;
  baseline_eval: EvalTask;
  summary_delta: {
    current_pass_rate: number;
    baseline_pass_rate: number;
    pass_rate_delta: number;
    current_fail_count: number;
    baseline_fail_count: number;
    fail_count_delta: number;
    current_error_count: number;
    baseline_error_count: number;
    error_count_delta: number;
  };
  metric_deltas: ReportCompareMetricDelta[];
  row_changes: Record<string, ReportCompareRowItem[]>;
}

export interface BlindTestTarget {
  target_type: 'llm_config' | 'endpoint';
  name: string;
  llm_config_id?: number | null;
  endpoint_url?: string | null;
  transport_mode?: 'json' | 'sse';
  authorization?: string | null;
  extra_headers?: string | null;
  request_body_template?: string | null;
  response_mode?: 'answer_only' | 'answer_with_contexts';
}

export interface BlindTestTask {
  id: number;
  name: string;
  dataset_id: number;
  status: string;
  progress: number;
  total_rows: number | null;
  completed_rows: number;
  voted_rows: number;
  sample_limit?: number | null;
  error_message?: string | null;
  summary?: Record<string, any> | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  target_a: BlindTestTarget;
  target_b: BlindTestTarget;
  dataset?: Dataset;
}

export interface BlindTestRowResult {
  id: number;
  blind_test_task_id: number;
  dataset_row_id: number;
  row_index: number;
  answer_a?: string | null;
  answer_b?: string | null;
  answer_a_error?: string | null;
  answer_b_error?: string | null;
  display_order: string[];
  vote?: 'left' | 'right' | 'tie' | 'both_bad' | 'skip' | null;
  vote_note?: string | null;
  voted_at?: string | null;
  created_at: string;
  dataset_row?: DatasetRow;
}

export interface BlindTestSummary {
  blind_test_task: BlindTestTask;
  total_count: number;
  completed_count: number;
  voted_count: number;
  pending_vote_count: number;
  model_a_wins: number;
  model_b_wins: number;
  ties: number;
  both_bad: number;
  no_answer_rows: number;
}

export interface PaginatedResponse<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

export interface RagDatasetDocument {
  id: number;
  job_id: number;
  filename: string;
  file_path?: string | null;
  char_count: number;
  chunk_count: number;
  created_at: string;
}

export interface RagDatasetChunk {
  id: number;
  document_id: number;
  chunk_index: number;
  chunk_key: string;
  content: string;
  char_count: number;
  suggested_question_count: number;
  allocated_question_count: number;
  quality_label: 'good' | 'medium' | 'low' | 'filtered';
  quality_score: number;
  quality_reasons: string[];
  generation_status: string;
  generation_error?: string | null;
  created_at: string;
}

export interface RagDatasetSample {
  id: number;
  job_id: number;
  document_id: number;
  chunk_id?: number | null;
  dataset_row_id?: number | null;
  question: string;
  reference: string;
  reference_context_ids: string[];
  source_chunk_ids: string[];
  status: string;
  error_message?: string | null;
  retry_count: number;
  selected: boolean;
  created_at: string;
  updated_at?: string | null;
}

// ======================== RSI ========================

export interface RsiBudget {
  max_iterations?: number | null;
  max_rows_per_iteration?: number | null;
  max_llm_calls?: number | null;
  max_minutes?: number | null;
  max_proposals_per_iteration?: number | null;
  max_consecutive_no_gain?: number | null;
}

export interface RsiUsage {
  llm_calls?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  elapsed_ms?: number;
  evaluations?: number;
  consecutive_no_gain?: number;
}

export interface RsiMetricStat {
  mean?: number | null;
  min?: number | null;
  max?: number | null;
  count?: number;
  error_count?: number;
  pass_rate?: number | null;
}

export interface RsiSliceSummary {
  total?: number;
  pass_count?: number;
  fail_count?: number;
  error_count?: number;
  pass_rate?: number;
  error_rate?: number;
  native_pass_rate?: number | null;
  metric_stats?: Record<string, RsiMetricStat>;
}

export interface RsiDeltaSlice {
  baseline?: RsiSliceSummary;
  candidate?: RsiSliceSummary;
  delta?: Record<string, any>;
}

export interface RsiDecisionObjective {
  mode?: string | null;
  metric?: string | null;
  baseline?: number | null;
  candidate?: number | null;
  gain?: number | null;
  target?: number | null;
  min_gain?: number | null;
}

export interface RsiDecisionCheck {
  name?: string;
  ok?: boolean;
  detail?: string;
}

export interface RsiDecisionMetrics {
  decision?: string;
  recommended?: string;
  reason?: string;
  objective?: RsiDecisionObjective;
  constraints?: RsiDecisionCheck[];
  violations?: string[];
  holdout?: {
    enabled?: boolean;
    rows?: number;
    train_rows?: number;
    min_rows_for_auto_accept?: number;
  };
  migration?: Record<string, any>;
  fitness?: number;
  auto_accept_eligible?: boolean;
}

export interface RsiMetricsDelta extends RsiDeltaSlice {
  train?: RsiDeltaSlice;
  holdout?: RsiDeltaSlice;
  decision_metrics?: RsiDecisionMetrics;
  objective?: RsiDecisionObjective;
  validation?: Record<string, any>;
  reference_thresholds?: Record<string, number>;
}

export interface RsiDiagnosisCluster {
  label?: string;
  root_cause_type?: string;
  affected_metric?: string;
  evidence_row_ids?: number[];
  suggested_lever?: string;
  severity?: string;
  size?: number;
}

export interface RsiDiagnosis {
  summary?: string;
  clusters?: RsiDiagnosisCluster[];
  sample_row_ids?: number[];
  fallback?: boolean;
  fallback_reason?: string | null;
  train_rows?: number;
  failed_rows?: number;
  llm_usage?: Record<string, any> | null;
}

export interface RsiProposal {
  id: number;
  loop_id: number;
  iteration_id: number;
  target_type: string;
  target_id?: number | null;
  field: string;
  operation: string;
  before_value?: unknown;
  after_value?: unknown;
  rationale?: string | null;
  evidence?: Record<string, any> | null;
  risk_level?: string | null;
  requires_review: boolean;
  status: string;
  applied_version_id?: number | null;
  decided_by?: string | null;
  decided_at?: string | null;
  decision_source?: string | null;
  created_at?: string | null;
  applied_at?: string | null;
}

export interface RsiIterationBrief {
  id: number;
  loop_id: number;
  iteration_index: number;
  status: string;
  baseline_eval_id?: number | null;
  candidate_eval_id?: number | null;
  proposal_count: number;
  objective_gain?: number | null;
  holdout_pass_rate?: number | null;
  cost?: Record<string, any> | null;
  decision?: string | null;
  decision_reason?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
}

export interface RsiIteration extends RsiIterationBrief {
  diagnosis?: RsiDiagnosis | null;
  metrics?: RsiMetricsDelta | null;
  cost?: Record<string, any> | null;
  proposals: RsiProposal[];
}

export interface RsiLoop {
  id: number;
  name: string;
  description?: string | null;
  status: string;
  baseline_eval_id: number;
  dataset_id: number;
  scenario_id: number;
  llm_config_id: number;
  proposer_llm_config_id?: number | null;
  evaluation_mode?: string | null;
  endpoint_target_id?: number | null;
  target_config?: Record<string, any> | null;
  response_mapping?: Record<string, any> | null;
  result_save_mode?: string | null;
  objective_metric?: string | null;
  objective_target?: number | null;
  objective_mode?: string | null;
  reference_thresholds?: Record<string, number> | null;
  holdout_config?: Record<string, any> | null;
  acceptance_policy?: Record<string, any> | null;
  budget?: RsiBudget | null;
  usage?: RsiUsage | null;
  current_iteration?: number;
  best_iteration_id?: number | null;
  final_eval_id?: number | null;
  auto_apply_low_risk: boolean;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  dataset_name?: string | null;
  scenario_name?: string | null;
  llm_model_name?: string | null;
  proposer_model_name?: string | null;
  best_gain?: number | null;
  best_iteration?: RsiIterationBrief | null;
  latest_iteration?: RsiIterationBrief | null;
}

export interface RsiConfigVersion {
  id: number;
  loop_id?: number | null;
  iteration_id?: number | null;
  proposal_id?: number | null;
  scope: string;
  scope_id: number;
  version: number;
  snapshot?: Record<string, any> | null;
  patch?: Record<string, any> | null;
  parent_version_id?: number | null;
  actor?: string | null;
  created_at?: string | null;
  rolled_back_at?: string | null;
}

export interface RsiLogs {
  loop_id: number;
  status: string;
  current_iteration: number;
  logs: string;
}

export interface RsiPreviewResult {
  success: boolean;
  message: string;
  row_id?: number | null;
  row_data?: Record<string, any> | null;
  metric_scores?: Record<string, any>;
  is_pass?: boolean | null;
  warnings: string[];
  errors: string[];
}

export interface RsiHardCaseResult {
  dataset_id: number;
  dataset_name: string;
  created_rows: number;
  skipped_row_ids: number[];
}

export interface RsiCreatePayload {
  name: string;
  description?: string | null;
  baseline_eval_id: number;
  llm_config_id?: number | null;
  proposer_llm_config_id?: number | null;
  objective_metric?: string | null;
  objective_mode?: 'metric_mean' | 'reference_pass_rate';
  objective_target?: number | null;
  budget?: RsiBudget;
  holdout?: {
    holdout_ratio?: number;
    min_rows?: number;
    min_rows_for_auto_accept?: number;
  };
  auto_apply_low_risk?: boolean;
}

export interface RagDatasetJob {
  id: number;
  name: string;
  description?: string | null;
  status: string;
  question_count_mode: 'auto' | 'custom';
  requested_question_count?: number | null;
  suggested_question_count?: number | null;
  total_documents: number;
  total_chunks: number;
  total_samples: number;
  completed_samples: number;
  failed_samples: number;
  error_message?: string | null;
  logs: string;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at?: string | null;
  dataset_id?: number | null;
  dataset?: Dataset | null;
  question_llm_config?: LLMConfig | null;
  documents: RagDatasetDocument[];
  generation_summary?: {
    supported_metrics: string[];
    unsupported_metrics: string[];
    notes: string[];
  };
}
