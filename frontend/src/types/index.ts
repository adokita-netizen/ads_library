export interface Ad {
  id: number;
  external_id?: string;
  title?: string;
  description?: string;
  platform: string;
  status: string;
  category?: string;
  video_url?: string;
  s3_key?: string;
  duration_seconds?: number;
  advertiser_name?: string;
  brand_name?: string;
  estimated_ctr?: number;
  view_count?: number;
  tags?: string[];
  created_at: string;
  updated_at: string;
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
