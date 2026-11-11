export interface CandlestickPoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface LinePoint {
  time: string;
  value: number | null;
}

export interface IndicatorSeries {
  name: string;
  pane: "overlay" | "oscillator";
  color: string;
  points: LinePoint[];
}

export interface ChartSpec {
  id: string;
  title: string;
  ticker: string;
  chart_type: "candlestick" | "comparison_line" | "projection_cone";
  candlesticks: CandlestickPoint[];
  series: IndicatorSeries[];
  subtitle?: string | null;
}

export interface TableSpec {
  id: string;
  title: string;
  columns: string[];
  rows: (string | number | null)[][];
  subtitle?: string | null;
}

export interface Citation {
  source: string;
  label: string;
  url?: string | null;
  retrieved_at: string;
}

export interface Assumption {
  key: string;
  value: string;
  rationale?: string | null;
}

export interface AnalysisResponse {
  conversation_id: string;
  message_id: string;
  narrative: string;
  tickers: string[];
  charts: ChartSpec[];
  tables: TableSpec[];
  citations: Citation[];
  assumptions: Assumption[];
  tools_used: string[];
  job_id?: string | null;
  disclaimer: string;
}

export interface JobRecord {
  job_id: string;
  job_type: string;
  tickers: string[];
  status: "PENDING" | "STARTED" | "PROGRESS" | "RETRY" | "SUCCESS" | "FAILURE";
  progress: number;
  stage: string;
  message: string;
  retries: number;
  result?: AnalysisResponse | null;
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}
