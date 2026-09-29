export type Capability = {
  capabilityId: string;
  domain: string;
  runtimeAgent: string;
  name: string;
  primaryOutput: string;
  contractKind: string;
  implementationStatus: string;
  sourceBranch: string;
  liveStatus?: string;
  lastRunAt?: string | null;
  lastRunId?: string | null;
};

export type Recommendation = {
  id: string;
  recommendationId?: string;
  capabilityId?: string;
  domain?: string;
  recommendationType?: string;
  subjectType?: string;
  subjectId?: string;
  action?: Record<string, unknown>;
  confidence?: number;
  riskLevel?: string;
  status: string;
  createdAt?: string;
  updatedAt?: string;
};

export type AgentEvent = {
  id: string;
  eventId?: string;
  eventType?: string;
  sourceAgent?: string;
  status?: string;
  createdAt?: string;
  payload?: Record<string, unknown>;
};

export type AgentRun = {
  id: string;
  runId?: string;
  capabilityId?: string;
  domain?: string;
  status?: string;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
};

export type AgentState = {
  id: string;
  stateId?: string;
  capabilityId?: string;
  domain?: string;
  outputType?: string;
  entityType?: string;
  entityId?: string;
  confidence?: number;
  riskLevel?: string;
  generatedAt?: string;
  payload?: Record<string, unknown>;
};

export type Workspace = {
  connected: boolean;
  business: { id: string; name?: string };
  capabilities: Capability[];
  recommendations: Recommendation[];
  events: AgentEvent[];
  runs: AgentRun[];
  state: AgentState[];
  outcomes: Array<Record<string, unknown>>;
  backendStatus: {
    currentStatus: string;
    remainingBeforeProductionDeploy?: string[];
  };
  demandStatus: {
    status: string;
    deploymentAllowed: boolean;
  };
  analysis: {
    status: string;
    dataUpdatedAt?: string | null;
    lastProcessedAt?: string | null;
    activeRunId?: string | null;
    processingRunId?: string | null;
    lastError?: string | null;
  };
  summary: {
    reviewCount: number;
    runningCount: number;
    failedCount: number;
    recentEventCount: number;
  };
};

export type ProcessingDomainReadiness = {
  key: string;
  label: string;
  status: 'READY' | 'PARTIAL' | 'NEEDS_DATA';
  detail: string;
  issues: string[];
};

export type ProcessingReadiness = {
  canProcess: boolean;
  analysisStatus: string;
  dataUpdatedAt?: string | null;
  lastProcessedAt?: string | null;
  activeAnalysisRunId?: string | null;
  processingRunId?: string | null;
  domains: ProcessingDomainReadiness[];
  counts: Record<string, number>;
};

export type ProcessingResult = {
  ok: true;
  runId: string;
  summary: {
    capabilities: number;
    results: number;
    recommendations: number;
    events: number;
    products: number;
    customers: number;
    completedDomains: number;
    skippedResults: number;
  };
};

export type DataFieldDefinition = {
  name: string;
  label: string;
  type: 'string' | 'number' | 'decimal' | 'percent' | 'boolean' | 'date' | 'datetime' | 'list' | 'enum' | 'textarea';
  required: boolean;
  options: string[] | null;
  default: unknown;
  lockedOnEdit: boolean;
  example: string | null;
};

export type DataSetDefinition = {
  key: string;
  label: string;
  group: string;
  description: string;
  collection: string;
  fields: DataFieldDefinition[];
  count: number;
};

export type DataValidationIssue = {
  row: number;
  field: string;
  message: string;
};

export type DataValidationResult = {
  valid: boolean;
  rowCount: number;
  validCount: number;
  errors: DataValidationIssue[];
  warnings: DataValidationIssue[];
  preview: Array<Record<string, unknown>>;
};

export type BusinessDataRecord = Record<string, unknown> & { id: string };
