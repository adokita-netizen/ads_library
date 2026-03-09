# B40: TypeScript 型安全性強化

## 問題
- `types/index.ts` に `any` 型が残存 → 型チェックが効かない
- APIレスポンスの型検証がない → サーバー側変更で実行時エラー
- optional フィールドが過剰 → 必須フィールドの欠落を検知できない

## 対象ファイル
- `frontend/src/types/index.ts`
- `frontend/src/lib/api.ts`

## 修正

### 1. `any` 型の排除
```tsx
// Before
ad_metadata?: any;
extra_data?: any;

// After
ad_metadata?: Record<string, string | number | boolean | null>;
extra_data?: Record<string, unknown>;
```

### 2. API レスポンスの型ガード
```tsx
// api.ts にレスポンス検証を追加
function assertAdResponse(data: unknown): asserts data is Ad {
  if (!data || typeof data !== "object") throw new Error("Invalid response");
  if (!("id" in data) || !("ad_id" in data)) throw new Error("Missing required fields");
}

// 使用箇所
const response = await fetch(url);
const data = await response.json();
assertAdResponse(data);
return data;
```

### 3. optional フィールドの整理
```tsx
// 必須フィールドと optional フィールドを明確に分離
interface Ad {
  // 必須（APIが常に返す）
  id: number;
  ad_id: string;
  page_name: string;

  // optional（条件付きで存在）
  snapshot_url?: string;
  video_url?: string | null;
  ad_metadata?: Record<string, string | number | boolean | null>;
}
```

## 制約
- `types/index.ts` と `api.ts` のみ修正
- 既存コンポーネントのインターフェースは維持（breaking change なし）
