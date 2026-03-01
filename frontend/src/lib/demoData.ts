// ─── Demo / Sample Data for Progressive Onboarding ───

export interface DemoAdItem {
  ad_id: number;
  product_name: string;
  advertiser_name: string;
  genre: string;
  platform: string;
  hit_score: number;
  trend_score: number;
  cumulative_views: number;
  cumulative_spend: number;
  days_running: number;
  is_still_running: boolean;
  creative_type: string;
  hook_type: string;
  thumbnail: string;
  rank: number;
}

export interface DemoRankings {
  items: DemoAdItem[];
  total: number;
}

export interface DemoWeeklyTrend {
  week: string;
  ad_count: number;
  hit_count: number;
  avg_score: number;
}

export interface DemoTrends {
  weekly: DemoWeeklyTrend[];
}

// ─── Sample Ads ───

export const DEMO_ADS: DemoAdItem[] = [
  {
    ad_id: 90001,
    product_name: "プレミアムリフトセラム",
    advertiser_name: "株式会社ビューティーラボ",
    genre: "美容",
    platform: "meta",
    hit_score: 92,
    trend_score: 88,
    cumulative_views: 1250000,
    cumulative_spend: 3800000,
    days_running: 45,
    is_still_running: true,
    creative_type: "video",
    hook_type: "before_after",
    thumbnail: "",
    rank: 1,
  },
  {
    ad_id: 90002,
    product_name: "スーパー酵素グリーン",
    advertiser_name: "ヘルスケア株式会社",
    genre: "健康食品",
    platform: "youtube",
    hit_score: 87,
    trend_score: 79,
    cumulative_views: 980000,
    cumulative_spend: 2900000,
    days_running: 30,
    is_still_running: true,
    creative_type: "video",
    hook_type: "testimonial",
    thumbnail: "",
    rank: 2,
  },
  {
    ad_id: 90003,
    product_name: "スリムボディEX",
    advertiser_name: "ダイエットサポート株式会社",
    genre: "ダイエット",
    platform: "tiktok",
    hit_score: 85,
    trend_score: 91,
    cumulative_views: 2100000,
    cumulative_spend: 1500000,
    days_running: 14,
    is_still_running: true,
    creative_type: "video",
    hook_type: "problem_agitation",
    thumbnail: "",
    rank: 3,
  },
  {
    ad_id: 90004,
    product_name: "モイスチャーリペアクリーム",
    advertiser_name: "ナチュラルスキン株式会社",
    genre: "スキンケア",
    platform: "instagram",
    hit_score: 82,
    trend_score: 74,
    cumulative_views: 650000,
    cumulative_spend: 2200000,
    days_running: 60,
    is_still_running: true,
    creative_type: "image",
    hook_type: "benefit_first",
    thumbnail: "",
    rank: 4,
  },
  {
    ad_id: 90005,
    product_name: "マルチビタミンプロ",
    advertiser_name: "サプリメントワークス",
    genre: "サプリメント",
    platform: "meta",
    hit_score: 78,
    trend_score: 70,
    cumulative_views: 520000,
    cumulative_spend: 1800000,
    days_running: 25,
    is_still_running: false,
    creative_type: "video",
    hook_type: "question",
    thumbnail: "",
    rank: 5,
  },
  {
    ad_id: 90006,
    product_name: "ハイドレーションミスト",
    advertiser_name: "株式会社ビューティーラボ",
    genre: "美容",
    platform: "youtube",
    hit_score: 76,
    trend_score: 82,
    cumulative_views: 430000,
    cumulative_spend: 1400000,
    days_running: 18,
    is_still_running: true,
    creative_type: "video",
    hook_type: "social_proof",
    thumbnail: "",
    rank: 6,
  },
  {
    ad_id: 90007,
    product_name: "ファイバーダイエットゼリー",
    advertiser_name: "ダイエットサポート株式会社",
    genre: "ダイエット",
    platform: "tiktok",
    hit_score: 73,
    trend_score: 85,
    cumulative_views: 890000,
    cumulative_spend: 900000,
    days_running: 10,
    is_still_running: true,
    creative_type: "video",
    hook_type: "curiosity",
    thumbnail: "",
    rank: 7,
  },
  {
    ad_id: 90008,
    product_name: "コラーゲンブースター5000",
    advertiser_name: "ヘルスケア株式会社",
    genre: "健康食品",
    platform: "meta",
    hit_score: 71,
    trend_score: 65,
    cumulative_views: 310000,
    cumulative_spend: 1100000,
    days_running: 35,
    is_still_running: false,
    creative_type: "image",
    hook_type: "authority",
    thumbnail: "",
    rank: 8,
  },
  {
    ad_id: 90009,
    product_name: "UVプロテクトジェル SPF50+",
    advertiser_name: "ナチュラルスキン株式会社",
    genre: "スキンケア",
    platform: "instagram",
    hit_score: 68,
    trend_score: 72,
    cumulative_views: 280000,
    cumulative_spend: 800000,
    days_running: 22,
    is_still_running: true,
    creative_type: "carousel",
    hook_type: "seasonal",
    thumbnail: "",
    rank: 9,
  },
  {
    ad_id: 90010,
    product_name: "鉄分チャージタブレット",
    advertiser_name: "サプリメントワークス",
    genre: "サプリメント",
    platform: "youtube",
    hit_score: 64,
    trend_score: 60,
    cumulative_views: 190000,
    cumulative_spend: 600000,
    days_running: 40,
    is_still_running: false,
    creative_type: "video",
    hook_type: "statistic",
    thumbnail: "",
    rank: 10,
  },
];

// ─── Rankings wrapper ───

export const DEMO_RANKINGS: DemoRankings = {
  items: DEMO_ADS,
  total: 10,
};

// ─── Trend data (4 weeks) ───

export const DEMO_TRENDS: DemoTrends = {
  weekly: [
    { week: "2026-02-09", ad_count: 42, hit_count: 5, avg_score: 61.3 },
    { week: "2026-02-16", ad_count: 48, hit_count: 7, avg_score: 64.8 },
    { week: "2026-02-23", ad_count: 55, hit_count: 9, avg_score: 67.2 },
    { week: "2026-03-01", ad_count: 58, hit_count: 10, avg_score: 70.1 },
  ],
};

// ─── Demo mode helpers ───

const DEMO_MODE_KEY = "vaap_demo_mode";

export function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(DEMO_MODE_KEY) === "true";
  } catch {
    return false;
  }
}

export function setDemoMode(on: boolean): void {
  if (typeof window === "undefined") return;
  try {
    if (on) {
      localStorage.setItem(DEMO_MODE_KEY, "true");
    } else {
      localStorage.removeItem(DEMO_MODE_KEY);
    }
  } catch {
    // localStorage unavailable
  }
}
