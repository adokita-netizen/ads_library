# B38: エラーハンドリング改善

## 問題
- `HitAdAnalysisView.tsx`: `Promise.all` で1つ失敗すると全データ消失 → `Promise.allSettled` にすべき
- API呼び出しエラー時にユーザーへのフィードバックが不十分（console.error のみ）
- クリップボードコピー失敗時のフォールバック処理なし

## 対象ファイル
- `frontend/src/components/HitAdAnalysisView.tsx`
- `frontend/src/components/AdLibrary.tsx`
- `frontend/src/lib/api.ts`

## 修正

### 1. Promise.all → Promise.allSettled
```tsx
// Before
const [rankings, metrics, ads] = await Promise.all([
  fetchRankings(), fetchMetrics(), fetchAds()
]);

// After
const [rankingsResult, metricsResult, adsResult] = await Promise.allSettled([
  fetchRankings(), fetchMetrics(), fetchAds()
]);
const rankings = rankingsResult.status === "fulfilled" ? rankingsResult.value : [];
const metrics = metricsResult.status === "fulfilled" ? metricsResult.value : [];
const ads = adsResult.status === "fulfilled" ? adsResult.value : [];
// 失敗した項目はトーストで通知
```

### 2. API エラーのユーザー通知
```tsx
// api.ts の共通エラーハンドラ
function handleApiError(error: unknown, context: string): never {
  const message = error instanceof Error ? error.message : "Unknown error";
  console.error(`[${context}]`, error);
  // toast通知やエラーステートへの反映
  throw new Error(`${context}: ${message}`);
}
```

### 3. クリップボード操作のフォールバック
```tsx
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // フォールバック: textarea経由
    const textarea = document.createElement("textarea");
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  }
}
```

## 制約
- UI レイアウトは変更しない
- 既存の正常系動作に影響を与えない
