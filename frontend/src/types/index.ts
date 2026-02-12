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
