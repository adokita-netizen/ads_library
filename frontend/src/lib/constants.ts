/** Shared platform labels (short abbreviation for badges/icons). */
export const platformLabels: Record<string, string> = {
  youtube: "YT",
  shorts: "S",
  tiktok: "TT",
  meta: "Meta",
  facebook: "FB",
  instagram: "IG",
  line: "L",
  yahoo: "Y!",
  x_twitter: "X",
  x: "X",
  pinterest: "Pin",
  smartnews: "SN",
  google_ads: "G",
  gunosy: "Gn",
};

/** Platform CSS class for icon badges (platform-icon variant). */
export const platformColors: Record<string, string> = {
  youtube: "platform-youtube",
  shorts: "bg-red-400",
  tiktok: "platform-tiktok",
  meta: "platform-meta",
  facebook: "platform-facebook",
  instagram: "platform-instagram",
  line: "platform-line",
  yahoo: "platform-yahoo",
  x_twitter: "platform-x",
  x: "platform-x",
  pinterest: "bg-red-600",
  smartnews: "bg-sky-600",
  google_ads: "bg-blue-500",
  gunosy: "bg-orange-500",
};

/** Platform badge CSS class (text-color variant for inline badges). */
export const platformBadgeColors: Record<string, string> = {
  youtube: "bg-red-100 text-red-800",
  tiktok: "bg-gray-900 text-white",
  meta: "bg-blue-100 text-blue-800",
  instagram: "bg-purple-100 text-purple-800",
  facebook: "bg-blue-100 text-blue-800",
  x_twitter: "bg-gray-100 text-gray-800",
  x: "bg-gray-100 text-gray-800",
  line: "bg-green-100 text-green-800",
  yahoo: "bg-red-50 text-red-700",
  pinterest: "bg-red-100 text-red-700",
  smartnews: "bg-sky-100 text-sky-800",
  google_ads: "bg-blue-100 text-blue-700",
  gunosy: "bg-orange-100 text-orange-800",
};

/** Genre filter options shared across views. */
export const genreOptions: { value: string; label: string }[] = [
  { value: "all", label: "全ジャンル" },
  { value: "ec_d2c", label: "EC・D2C" },
  { value: "app", label: "アプリ" },
  { value: "finance", label: "金融" },
  { value: "education", label: "教育" },
  { value: "beauty", label: "美容・コスメ" },
  { value: "food", label: "食品" },
  { value: "gaming", label: "ゲーム" },
  { value: "health", label: "健康食品" },
  { value: "technology", label: "テクノロジー" },
  { value: "real_estate", label: "不動産" },
  { value: "travel", label: "旅行" },
  { value: "other", label: "その他" },
];
