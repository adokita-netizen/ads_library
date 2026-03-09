# フィーチャーフラグ視点 — 壊れた機能を安全に隠す・有効化する

## なぜフィーチャーフラグが必要か

22ビューのうち半数以上が「コードはあるが動くか不明」状態。
壊れた機能をユーザーに見せない仕組みが必要。

---

## 方法 1: サイドバーでビュー非表示 (最簡単)

### 現状の Sidebar.tsx
全21ナビゲーション項目が表示されている。

### 対策: 動作確認済みビューのみ表示
```typescript
// frontend/src/components/common/Sidebar.tsx

const ENABLED_VIEWS = [
  "pro-database",    // ✅ 確認済み
  "search",          // ✅ 確認済み
  "hit-ads",         // ✅ 確認済み
  "trend",           // ⚠️ 要確認
  "analysis",        // ⚠️ 要確認
  "settings",        // ✅ 確認済み
];

// navSections 内でフィルタリング
const filteredSections = navSections.map(section => ({
  ...section,
  items: section.items.filter(item => ENABLED_VIEWS.includes(item.id))
}));
```

### メリット
- 変更1ファイル、数行
- 壊れたビューにユーザーがアクセスできない
- 機能が安定したら配列に追加するだけ

---

## 方法 2: 環境変数ベースのフラグ

### バックエンド (Python)
```python
# backend/app/core/config.py
import os

FEATURE_FLAGS = {
    "AI_GENERATION": os.getenv("FF_AI_GENERATION", "false") == "true",
    "LP_ANALYSIS": os.getenv("FF_LP_ANALYSIS", "false") == "true",
    "META_INTEGRATION": os.getenv("FF_META_INTEGRATION", "false") == "true",
    "TEAM_FEATURES": os.getenv("FF_TEAM_FEATURES", "false") == "true",
    "SCENARIO_BUILDER": os.getenv("FF_SCENARIO_BUILDER", "false") == "true",
}

# エンドポイントで使用
@router.get("/creative/generate")
async def generate_creative():
    if not FEATURE_FLAGS["AI_GENERATION"]:
        raise HTTPException(503, "AI generation is not enabled")
    ...
```

### フロントエンド (Next.js)
```typescript
// frontend/src/lib/featureFlags.ts
export const FEATURES = {
  AI_GENERATION: process.env.NEXT_PUBLIC_FF_AI_GENERATION === 'true',
  LP_ANALYSIS: process.env.NEXT_PUBLIC_FF_LP_ANALYSIS === 'true',
  META_INTEGRATION: process.env.NEXT_PUBLIC_FF_META_INTEGRATION === 'true',
  TEAM_FEATURES: process.env.NEXT_PUBLIC_FF_TEAM_FEATURES === 'true',
  SCENARIO_BUILDER: process.env.NEXT_PUBLIC_FF_SCENARIO_BUILDER === 'true',
};

// Sidebar.tsx で使用
const navItems = allNavItems.filter(item => {
  if (item.id === 'ai-expert' && !FEATURES.AI_GENERATION) return false;
  if (item.id === 'lp-analysis' && !FEATURES.LP_ANALYSIS) return false;
  if (item.id === 'meta-ads' && !FEATURES.META_INTEGRATION) return false;
  if (item.id === 'team' && !FEATURES.TEAM_FEATURES) return false;
  return true;
});
```

---

## 方法 3: API ベースのフラグ (最も柔軟)

### エンドポイント
```python
@router.get("/settings/feature-flags")
async def get_feature_flags():
    """Return enabled features based on current state."""
    return {
        "pro_database": True,
        "search": True,
        "hit_ads": True,
        "trend": check_trend_data_exists(),
        "ai_generation": check_api_keys_set("openai", "anthropic"),
        "lp_analysis": check_playwright_available(),
        "meta_integration": check_meta_token_valid(),
        "team_features": False,  # Not ready
        "scenario_builder": check_api_keys_set("openai"),
        "export": True,
    }

def check_api_keys_set(*providers):
    """Check if API keys are configured."""
    # DB から api_keys テーブルを確認
    ...

def check_meta_token_valid():
    """Check if Meta API token is still valid."""
    # Meta API に軽いリクエストを送って確認
    ...

def check_trend_data_exists():
    """Check if there's enough data for trends."""
    # ad_metrics に7日分以上のデータがあるか
    ...
```

### フロントで取得
```typescript
// page.tsx
const [features, setFeatures] = useState<Record<string, boolean>>({});

useEffect(() => {
  fetch('/api/v1/settings/feature-flags')
    .then(r => r.json())
    .then(setFeatures)
    .catch(() => {
      // フォールバック: 最低限の機能のみ
      setFeatures({ pro_database: true, search: true });
    });
}, []);
```

---

## 推奨: 方法1 + 方法3 の組み合わせ

### 即座にやること (方法1)
Sidebar.tsx で壊れたビューを非表示にする。5分で完了。

### 次にやること (方法3)
`/settings/feature-flags` エンドポイントを追加。
フロントが動的にビューの表示/非表示を切り替え。
APIキー設定→AI機能自動有効化、Meta トークン設定→Meta連携自動有効化。

---

## ビュー別のフラグ推奨

| ビュー | フラグ | 初期値 | 有効化条件 |
|--------|--------|--------|-----------|
| PRO DATABASE | 常時有効 | true | - |
| 検索 | 常時有効 | true | - |
| ヒット広告分析 | 常時有効 | true | - |
| トレンド | データ依存 | false | ad_metrics 7日分 |
| 分析 | 常時有効 | true | - |
| LP分析 | 機能依存 | false | Playwright稼働中 |
| 競合インテリジェンス | データ依存 | false | 500件以上 |
| 比較ツール | 常時有効 | true | - |
| AI専門家 | APIキー依存 | false | OpenAI/Anthropic キー |
| クリエイティブ生成 | APIキー依存 | false | OpenAI/Anthropic キー |
| シナリオ作成 | APIキー依存 | false | OpenAI キー |
| ブリーフ作成 | APIキー依存 | false | OpenAI キー |
| 自社広告管理 | トークン依存 | false | Meta APIトークン |
| レポート | 常時有効 | true | - |
| カレンダー | データ依存 | false | delivery_start_time |
| お知らせ | 機能依存 | false | 通知ロジック稼働 |
| コレクション | 常時有効 | true | - |
| チームスペース | 開発中 | false | v2.0 |
| キャンペーン | トークン依存 | false | Meta APIトークン |
| マイリスト | 常時有効 | true | - |
| VAAPストア | 開発中 | false | v3.0 |
| 設定 | 常時有効 | true | - |

### 初期有効ビュー数: 10/22
壊れないビューだけ表示 → プロダクトが壊れて見えない
