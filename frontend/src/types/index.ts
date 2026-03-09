export interface Ad {
  id: number;
  external_id?: string;
  title?: string;
  description?: string;
  platform: string;
  status: string;
  category?: string;
  creative_type?: string;
  video_url?: string;
  s3_key?: string;
  thumbnail_url?: string;
  image_url?: string;
  image_s3_key?: string;
  all_image_urls?: string[];
  snapshot_url?: string;
  media_extraction_status?: string;
  duration_seconds?: number;
  advertiser_name?: string;
  brand_name?: string;
  estimated_ctr?: number;
  view_count?: number;
  spend?: number;
  impressions?: number;
  reach?: number;
  cpc?: number;
  cpm?: number;
  frequency?: number;
  destination_url?: string;
  destination_type?: string;
  final_url?: string;
  resolved_url?: string;
  domain?: string;
  lp_status?: string;
  lp_score?: number;
  language?: string;
  language_source?: string;
  exclude_from_analysis?: boolean;
  exclude_reason?: string;
  jp_char_ratio?: number;
  topic_label?: string;
  topic_confidence?: number;
  matched_terms?: string[];
  needs_topic_review?: boolean;
  review_required?: boolean;
  review_reason?: string;
  topic_provenance?: string;
  classification_provenance?: string;
  topic_source?: string;
  classification_source?: string;
  priority?: "high" | "medium" | "low" | string;
  priority_level?: "high" | "medium" | "low" | string;
  priority_score?: number;
  actual_metrics_priority?: "high" | "medium" | "low" | string;
  actual_metrics_priority_score?: number;
  media_status?: MediaStatus;
  media_cache_status?: string;
  metric_source?: string;
  creative_source?: string;
  lp_source?: string;
  metric_status?: "real" | "estimated" | "missing" | "stale" | string;
  creative_status?: "real" | "estimated" | "missing" | "stale" | string;
  freshness_status?: "fresh" | "missing" | "stale" | string;
  last_meta_success_at?: string;
  meta_quality_state?: "real" | "estimated" | "missing" | "stale" | string;
  meta_recovery_reason?: string;
  tags?: string[];
  created_at: string;
  updated_at: string;
}

export interface MediaStatus {
  viewable?: boolean;
  downloadable?: boolean;
  has_lp?: boolean;
  primary_type?: string;
  missing_reasons?: string[];
}

export interface LPInfo {
  destination_url?: string;
  resolved_url?: string;
  redirect_chain?: string[];
  domain?: string;
  final_domain?: string;
  destination_type?: string;
  lp_status?: string;
  lp_score?: number | { score?: number | null } | null;
  has_lp?: boolean;
  http_status?: number | string | null;
}

export interface AdMediaInfo {
  ad_id: number;
  creative_type?: string;
  media_extraction_status?: string;
  image_url?: string;
  video_url?: string;
  snapshot_url?: string;
  download_url?: string;
  media_status?: MediaStatus;
  lp_info?: LPInfo;
}

export interface MetaTokenInfo {
  has_token: boolean;
  token_source: "db" | "env" | "missing" | string;
  runtime_source: "db" | "env" | "missing" | string;
  source_priority?: string[];
  fallback_used?: boolean;
  fallback_reason?: string | null;
  is_valid: boolean;
  app_id?: string | null;
  type?: string | null;
  expires_at?: number | null;
  days_remaining?: number | null;
  is_expiring?: boolean;
  scopes?: string[];
  user_id?: string | null;
  user_name?: string | null;
  last_validation_error?: string | null;
  message?: string | null;
}

export interface CreativeLibraryAuditRow {
  label: string;
  total_ads?: number;
  viewable_count?: number;
  downloadable_count?: number;
  lp_present_count?: number;
  lp_resolved_count?: number;
  missing_media_count?: number;
  download_unavailable_count?: number;
  missing_lp_count?: number;
  lp_unresolved_count?: number;
}

export interface CreativeLibraryAuditAd {
  ad_id: number;
  title: string;
  advertiser_name?: string;
  platform?: string;
  genre?: string;
  priority_score?: number;
  failure_reason_codes?: string[];
  needs_cr_recovery?: boolean;
  needs_download_recovery?: boolean;
  needs_lp_resolution?: boolean;
}

export interface CreativeLibraryDailyChange {
  ad_id: number;
  title: string;
  advertiser_name?: string;
  platform?: string;
  genre?: string;
  direction?: string;
  delta_score?: number;
  failure_reason_codes?: string[];
}

export interface CreativeLibraryAudit {
  summary: {
    total_ads: number;
    creative_viewable_rate: number;
    creative_downloadable_rate: number;
    lp_present_rate: number;
    lp_resolved_rate: number;
    missing_media_count?: number;
    missing_lp_count?: number;
  };
  platform_breakdown: CreativeLibraryAuditRow[];
  genre_breakdown: CreativeLibraryAuditRow[];
  priority_recovery_ads: CreativeLibraryAuditAd[];
  creative_library_daily_report?: {
    top_regressions: CreativeLibraryDailyChange[];
    top_recoveries: CreativeLibraryDailyChange[];
    worsening_segments?: Array<{
      segment_type?: string;
      label?: string;
      metric?: string;
      delta?: number;
    }>;
  };
}

export interface CreativeLibraryAuditResponse {
  creative_library_audit: CreativeLibraryAudit;
}

export interface AdAnalysis {
  ad_id: number;
  total_scenes?: number;
  avg_scene_duration?: number;
  face_closeup_ratio?: number;
  product_display_ratio?: number;
  text_overlay_ratio?: number;
  is_ugc_style?: boolean;
  has_narration?: boolean;
  has_subtitles?: boolean;
  hook_type?: string;
  hook_text?: string;
  hook_score?: number;
  cta_text?: string;
  overall_sentiment?: string;
  sentiment_score?: number;
  full_transcript?: string;
  keywords?: Array<{ keyword: string; score: number; category: string }>;
  dominant_color_palette?: string[];
  winning_score?: number;
}

export interface DashboardStats {
  total_ads: number;
  analyzed_ads: number;
  analysis_rate: number;
  ads_by_platform: Record<string, number>;
  ads_by_category: Record<string, number>;
  avg_winning_score?: number;
  sentiment_distribution: Record<string, number>;
}

export interface PredictionResult {
  ad_id: number;
  predicted_ctr: number;
  ctr_confidence: { low: number; high: number };
  predicted_cvr: number;
  cvr_confidence: { low: number; high: number };
  winning_probability: number;
  optimal_duration_seconds: number;
  feature_importance: Array<{
    feature: string;
    importance: number;
    value: string;
  }>;
  improvement_suggestions: Array<{
    category: string;
    suggestion: string;
    priority: string;
    expected_ctr_lift?: string;
  }>;
}

export interface FatigueResult {
  ad_id: number;
  fatigue_score: number;
  days_active: number;
  performance_trend: string;
  estimated_remaining_days: number;
  recommendation: string;
  replacement_urgency: string;
  metrics_trend: Record<string, number>;
}

export interface GeneratedScript {
  title: string;
  total_duration_seconds: number;
  sections: Array<{
    section_name: string;
    duration_seconds: number;
    narration: string;
    visual_description: string;
    text_overlay: string;
    audio_notes: string;
  }>;
  thumbnail_concept: string;
  hashtags: string[];
  a_b_test_notes: string;
}

// LP Analysis types
export interface LandingPageSummary {
  id: number;
  url: string;
  final_url?: string;
  domain?: string;
  title?: string;
  meta_description?: string;
  lp_type: string;
  genre?: string;
  advertiser_name?: string;
  product_name?: string;
  status: string;
  word_count?: number;
  image_count?: number;
  cta_count?: number;
  testimonial_count?: number;
  estimated_read_time_seconds?: number;
  hero_headline?: string;
  primary_cta_text?: string;
  has_pricing?: boolean;
  price_text?: string;
  crawled_at?: string;
  analyzed_at?: string;
  created_at: string;
}

export interface LPSection {
  section_order: number;
  section_type: string;
  heading?: string;
  body_text?: string;
  has_image: boolean;
  has_video: boolean;
  has_cta: boolean;
  cta_text?: string;
}

export interface USPPattern {
  id: number;
  usp_category: string;
  usp_text: string;
  usp_headline?: string;
  supporting_evidence?: string;
  prominence_score?: number;
  position_in_page?: string;
  keywords?: string[];
}

export interface AppealAxis {
  appeal_axis: string;
  strength_score: number;
  evidence_texts?: string[];
}

export interface LPAnalysisDetail {
  overall_quality_score?: number;
  conversion_potential_score?: number;
  trust_score?: number;
  urgency_score?: number;
  page_flow_pattern?: string;
  structure_summary?: string;
  inferred_target_gender?: string;
  inferred_target_age_range?: string;
  inferred_target_concerns?: string[];
  target_persona_summary?: string;
  primary_appeal_axis?: string;
  secondary_appeal_axis?: string;
  appeal_strategy_summary?: string;
  competitive_positioning?: string;
  differentiation_points?: string[];
  headline_effectiveness?: number;
  cta_effectiveness?: number;
  emotional_triggers?: string[];
  power_words?: string[];
  strengths?: string[];
  weaknesses?: string[];
  reusable_patterns?: string[];
  improvement_suggestions?: string[];
  full_analysis_text?: string;
}

export interface CompetitorAppealPattern {
  appeal_axis: string;
  avg_strength: number;
  usage_count: number;
  sample_texts: string[];
}

export interface GenreInsight {
  genre: string;
  total_lps_analyzed: number;
  dominant_appeal: string;
  appeal_distribution: CompetitorAppealPattern[];
  common_usps: Array<{
    category: string;
    count: number;
    avg_prominence: number;
    top_keywords: string[];
    sample_texts: string[];
  }>;
  avg_quality_score: number;
  common_structures: string[];
  target_personas: Array<{
    gender: string;
    age_range: string;
    concerns: string[];
  }>;
}

export interface USPFlowRecommendation {
  recommended_primary_usp: string;
  recommended_appeal_axis: string;
  article_lp_structure: Array<{
    section: string;
    purpose: string;
    content_guide: string;
    appeal_technique: string;
  }>;
  headline_suggestions: string[];
  differentiation_opportunities: string[];
  competitor_gaps: string[];
  estimated_effectiveness: number;
  reasoning: string;
}

// Ranking types
export interface ProductRankingItem {
  rank: number;
  previous_rank?: number;
  rank_change?: number;
  ad_id: number;
  product_name?: string;
  advertiser_name?: string;
  genre?: string;
  platform?: string;
  view_increase: number;
  spend_increase: number;
  cumulative_views: number;
  cumulative_spend: number;
  is_hit: boolean;
  hit_score?: number;
  trend_score?: number;
}

export interface SearchResult {
  type: "ad" | "transcript" | "text_detection" | "landing_page";
  id: number;
  title?: string;
  matched_text?: string;
  platform?: string;
  advertiser_name?: string;
  match_field: string;
  created_at?: string;
}

export interface NotificationConfig {
  id: number;
  channel_type: string;
  webhook_url?: string;
  room_id?: string;
  notify_new_hit_ads: boolean;
  notify_competitor_activity: boolean;
  notify_ranking_change: boolean;
  notify_fatigue_warning: boolean;
  watched_genres?: string[];
  watched_advertisers?: string[];
  is_active: boolean;
}

export interface SavedItem {
  id: number;
  item_type: string;
  item_id: number;
  label?: string;
  notes?: string;
  folder?: string;
  created_at: string;
}

// Own LP types
export interface OwnLP extends LandingPageSummary {
  is_own: boolean;
  own_lp_label?: string;
  own_lp_version?: number;
  competitor_count_in_genre: number;
  avg_competitor_quality?: number;
  quality_rank_in_genre?: string;
}

export interface LPCompareAxisItem {
  axis: string;
  own_strength: number;
  competitor_avg: number;
  gap: number;
}

export interface LPCompareResult {
  own_lp: LandingPageSummary;
  competitor_count: number;
  own_quality: number;
  competitor_avg_quality: number;
  own_conversion: number;
  competitor_avg_conversion: number;
  own_trust: number;
  competitor_avg_trust: number;
  appeal_comparison: LPCompareAxisItem[];
  own_usps: USPPattern[];
  missing_usp_categories: string[];
  own_flow: string;
  common_competitor_flows: string[];
  strengths_vs_competitors: string[];
  improvement_opportunities: string[];
  quick_wins: string[];
}

// ==================== Competitive Intelligence Types ====================

// Spend estimation with confidence ranges
export interface SpendEstimateResult {
  ad_id: number;
  estimated_spend: number;
  confidence_ranges: {
    p10: number;
    p25: number;
    p50: number;
    p75: number;
    p90: number;
  };
  cpm_info: {
    platform_avg: number;
    genre_adjusted: number;
    seasonal_factor: number;
    user_calibrated?: number;
  };
  estimation_method: string;
  confidence_level: number;
}

export interface CPMCalibrationItem {
  id: number;
  platform: string;
  genre?: string;
  actual_cpm: number;
  actual_cpv?: number;
  notes?: string;
  created_at: string;
}

// Similarity search
export interface SimilarAdResult {
  ad_id: number;
  similarity: number;
  title?: string;
  platform?: string;
  advertiser_name?: string;
  auto_appeal_axes?: string[];
  auto_expression_type?: string;
  auto_structure_type?: string;
}

// Destination analytics
export interface LPReuseItem {
  url_hash: string;
  url: string;
  domain?: string;
  title?: string;
  genre?: string;
  product_name?: string;
  advertiser_count: number;
  ad_count: number;
  advertisers: string[];
}

export interface CreativeVariationResult {
  lp_id: number;
  url: string;
  domain?: string;
  title?: string;
  genre?: string;
  quality_score?: number;
  creative_count: number;
  advertiser_count: number;
  total_spend_30d: number;
  creatives: Array<{
    ad_id: number;
    title?: string;
    platform: string;
    advertiser_name?: string;
    duration_seconds?: number;
    total_spend_30d: number;
    total_views_30d: number;
  }>;
}

// Alert detection
export interface AlertItem {
  id: number;
  alert_type: string;
  severity: string;
  entity_type: string;
  entity_name?: string;
  title: string;
  description?: string;
  metric_before?: number;
  metric_after?: number;
  change_percent?: number;
  context_data?: Record<string, unknown>;
  is_dismissed: boolean;
  detected_at: string;
}

// Two-stage classification
export interface ClassificationTag {
  id: number;
  ad_id: number;
  field_name: string;
  value: string;
  confidence: number;
  status: string;
  classified_by: string;
  confirmed_by?: string;
  confirmed_at?: string;
  previous_value?: string;
}

// Trend prediction
export interface TrendPredictionItem {
  ad_id: number;
  momentum_score: number;
  hit_probability: number;
  predicted_hit: boolean;
  growth_phase: string;
  days_active?: number;
  velocity: {
    view_1d: number;
    view_3d: number;
    view_7d: number;
    view_acceleration: number;
    spend_1d: number;
    spend_3d: number;
    spend_7d: number;
    spend_acceleration: number;
  };
  genre?: string;
  genre_percentile?: number;
  predicted_peak_spend?: number;
  title?: string;
  platform?: string;
  advertiser_name?: string;
}

// LP Funnels
export interface FunnelItem {
  id: number;
  funnel_name?: string;
  root_domain?: string;
  advertiser_name?: string;
  genre?: string;
  product_name?: string;
  total_steps: number;
  funnel_type?: string;
  estimated_total_spend?: number;
  ad_count?: number;
  steps: Array<{
    step_order: number;
    step_type: string;
    url?: string;
    page_title?: string;
    estimated_dropoff_rate?: number;
  }>;
}

// Campaign types
export interface Campaign {
  id: number;
  name: string;
  description?: string;
  user_id: number;
  ad_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignAdItem {
  id: number;
  ad_id: number;
  notes?: string;
  created_at: string;
  title?: string;
  platform?: string;
  creative_type?: string;
  advertiser_name?: string;
  brand_name?: string;
  duration_seconds?: number;
  view_count?: number;
  image_url?: string;
  video_url?: string;
  thumbnail_url?: string;
  snapshot_url?: string;
}

export interface CampaignDetail {
  id: number;
  name: string;
  description?: string;
  user_id: number;
  ads: CampaignAdItem[];
  created_at: string;
  updated_at: string;
}

// ==================== Meta Marketing Types ====================

export interface MetaTokenStatus {
  has_token: boolean;
  is_valid: boolean;
  scopes: string[];
  has_required_scopes: boolean;
  missing_scopes: string[];
  has_management: boolean;
  expires_at?: number;
  days_remaining?: number;
  is_expiring: boolean;
  user_id?: string;
  user_name?: string;
  app_id?: string;
  token_type?: string;
  note?: string;
  error?: string;
}

export interface MetaAdAccount {
  id: number;
  user_id: number;
  account_id: string;
  account_name?: string;
  business_name?: string;
  currency: string;
  timezone_name: string;
  account_status?: number;
  last_synced_at?: string;
  sync_status: string;
  sync_error?: string;
  amount_spent?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MetaAvailableAccount {
  account_id: string;
  name?: string;
  business_name?: string;
  currency?: string;
  timezone_name?: string;
  account_status?: number;
  amount_spent?: string;
  is_connected: boolean;
}

export interface MetaCampaign {
  id: number;
  meta_id: string;
  account_id: string;
  name: string;
  status: string;
  effective_status: string;
  objective?: string;
  daily_budget?: string;
  lifetime_budget?: string;
  budget_remaining?: string;
  start_time?: string;
  stop_time?: string;
  buying_type?: string;
  special_ad_categories?: string[];
  created_at: string;
  updated_at: string;
}

export interface MetaAdSet {
  id: number;
  meta_id: string;
  campaign_meta_id: string;
  account_id: string;
  name: string;
  status: string;
  effective_status: string;
  daily_budget?: string;
  lifetime_budget?: string;
  bid_strategy?: string;
  bid_amount?: string;
  billing_event?: string;
  optimization_goal?: string;
  targeting?: Record<string, unknown>;
  start_time?: string;
  end_time?: string;
  created_at: string;
  updated_at: string;
}

export interface MetaAd {
  id: number;
  meta_id: string;
  ad_set_meta_id: string;
  account_id: string;
  name: string;
  status: string;
  effective_status: string;
  creative_id?: string;
  creative_thumbnail_url?: string;
  creative_body?: string;
  creative_title?: string;
  creative_link_url?: string;
  creative_image_url?: string;
  creative_video_url?: string;
  creative_type?: string;
  linked_ad_id?: number;
  created_at: string;
  updated_at: string;
}

export interface MetaInsight {
  id: number;
  account_id: string;
  entity_type: string;
  entity_id: string;
  date_start: string;
  date_stop: string;
  impressions: number;
  reach: number;
  clicks: number;
  spend: number;
  ctr: number;
  cpc: number;
  cpm: number;
  frequency: number;
  conversions?: number;
  conversion_values?: number;
  cost_per_conversion?: number;
}

export interface ABTestExperiment {
  id: number;
  user_id: number;
  account_id: string;
  name: string;
  description?: string;
  hypothesis?: string;
  status: string;
  test_type: string;
  primary_metric: string;
  confidence_level: number;
  min_sample_size: number;
  campaign_meta_id?: string;
  winner_variant_id?: number;
  statistical_significance?: number;
  started_at?: string;
  completed_at?: string;
  variants: ABTestVariant[];
  created_at: string;
  updated_at: string;
}

export interface ABTestVariant {
  id: number;
  experiment_id: number;
  name: string;
  variant_type: string;
  ad_set_meta_id?: string;
  ad_meta_id?: string;
  creative_meta_id?: string;
  variation_description?: string;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: number;
  ctr: number;
  cvr: number;
  cpa: number;
  is_winner: boolean;
}

export interface OptimizationRecommendation {
  id: number;
  user_id: number;
  account_id: string;
  entity_type: string;
  entity_id: string;
  entity_name?: string;
  recommendation_type: string;
  severity: string;
  title: string;
  description?: string;
  rationale?: string;
  predicted_impact?: {
    metric: string;
    current: number;
    predicted: number;
    change_percent: number;
  };
  action_payload?: Record<string, unknown>;
  status: string;
  applied_at?: string;
  user_feedback?: string;
  actual_impact?: Record<string, unknown>;
  expires_at?: string;
  created_at: string;
}

export interface CreativeInsightsSummary {
  account_id: string;
  creative_type_distribution: Record<string, number>;
  total_ads: number;
  top_performers: Array<{
    entity_id: string;
    total_spend: number;
    total_clicks: number;
    total_impressions: number;
    ctr: number;
  }>;
}

export interface CompetitorComparison {
  meta_ad_id: string;
  own_ad_name: string;
  own_scores: Record<string, number>;
  competitor_averages: Record<string, number>;
  advantages: string[];
  disadvantages: string[];
  suggestions: string[];
}

// ==================== Smart Insights Types ====================

export interface PerformanceSummary {
  account_id: string;
  period_days: number;
  current_period: PerformanceMetrics;
  previous_period: PerformanceMetrics;
  deltas: Record<string, number | null>;
}

export interface PerformanceMetrics {
  impressions: number;
  reach: number;
  clicks: number;
  spend: number;
  conversions: number;
  conversion_values: number;
  ctr: number;
  cpc: number;
  cpm: number;
  cpa: number;
  roas: number;
  avg_frequency: number;
}

export interface DailyTrendPoint {
  date: string;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
  ctr: number;
  cpc: number;
  cpa: number;
}

export interface DailyTrendsData {
  account_id: string;
  days: number;
  trends: DailyTrendPoint[];
}

export interface CreativePerformanceAd {
  meta_id: string;
  name: string;
  status: string;
  creative_type: string;
  creative_title?: string;
  creative_body?: string;
  creative_thumbnail_url?: string;
  creative_image_url?: string;
  creative_video_url?: string;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
  conversion_values: number;
  ctr: number;
  cpc: number;
  cpm: number;
  cpa: number;
  roas: number;
  video_thruplay?: number;
  video_completion_rate?: number;
  video_retention?: {
    p25: number;
    p50: number;
    p75: number;
    p100: number;
  };
}

export interface CreativeTypeSummary {
  count: number;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
  avg_ctr: number;
  avg_cpc: number;
  avg_cpa: number;
}

export interface CreativePerformanceData {
  account_id: string;
  period_days: number;
  ads: CreativePerformanceAd[];
  type_summary: Record<string, CreativeTypeSummary>;
}

export interface SmartInsight {
  category: string;
  severity: "critical" | "negative" | "warning" | "positive";
  title: string;
  description: string;
  metric: string;
  value: number;
  delta: number | null;
}

// LP Fingerprint
export interface LPFingerprintItem {
  id: number;
  snapshot_date: string;
  content_hash?: string;
  structure_hash?: string;
  offer_fingerprint?: string;
  offer_cluster_id?: number;
  offer_price?: string;
  offer_discount_percent?: number;
  offer_guarantee_text?: string;
  changes_detected?: string[];
  change_magnitude?: number;
}
