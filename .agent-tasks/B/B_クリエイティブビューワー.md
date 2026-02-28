# エージェントB: クリエイティブビューワー（フロントエンド）

## 概要
広告をクリックしても `ProductDetailModal` がメタデータしか表示せず、動画・静止画のプレビューができない。
ユーザーがクリエイティブを閲覧できるビューワーコンポーネントを作成する。

## プロジェクト情報
- パス: `C:\Users\ishit\ads_library`
- フロントエンド: `frontend/` (Next.js + React + TypeScript + Tailwind CSS)
- バックエンドAPI: `http://localhost:8000/api/v1`

## ブランチ名
`feat/creative-viewer`

## 対象ファイル
- `frontend/src/components/common/CreativeViewer.tsx` (新規作成)
- `frontend/src/components/analysis/ProductDetailModal.tsx` (修正)

## 手順

### 1. 既存コードの把握
まず以下のファイルを読んで現状を理解:
- `frontend/src/components/analysis/ProductDetailModal.tsx` — モーダルの構造
- `frontend/src/components/dashboard/AdLibrary.tsx` — 広告一覧のサムネイル表示
- `frontend/src/lib/api.ts` — APIクライアント（エンドポイント定義）

### 2. CreativeViewer コンポーネント作成

`frontend/src/components/common/CreativeViewer.tsx`:

```tsx
// Props定義
interface CreativeViewerProps {
  imageUrl?: string | null;
  videoUrl?: string | null;
  snapshotUrl?: string | null;
  thumbnailUrl?: string | null;
  creativeType?: string | null;  // "video" | "image" | "carousel" | "unknown"
}
```

表示ロジック（優先順位）:

1. **動画** (`videoUrl` あり、または `creativeType === "video"`):
   - `<video>` タグ: `controls`, `preload="metadata"`, `poster={thumbnailUrl}`
   - 再生ボタンのオーバーレイ
   - `playsInline` 属性（モバイル対応）

2. **静止画** (`imageUrl` あり):
   - `<img>` タグ: `object-fit: contain`, 最大高さ400px
   - クリックで拡大表示（オーバーレイ+backdrop）
   - `alt` にクリエイティブタイプを設定

3. **スナップショット** (`snapshotUrl` あり、他がない場合):
   - Facebookの ads/library URL → 外部リンクボタンで表示
   - `<a href={snapshotUrl} target="_blank">` で「広告を確認する」リンク
   - （iframeは Facebook が X-Frame-Options で拒否するため使わない）

4. **何もない場合**:
   - グレーのプレースホルダー
   - アイコン + 「クリエイティブなし」テキスト

スタイリング:
- `rounded-lg overflow-hidden bg-gray-100`
- 最大幅100%、最大高さ400px
- レスポンシブ（モバイル対応）
- 既存のTailwind設計言語に合わせる（`text-gray-600`, `border-gray-200` 等）

### 3. ProductDetailModal に組み込み

`ProductDetailModal.tsx` のOverviewタブ最上部に配置:

```tsx
import { CreativeViewer } from "../common/CreativeViewer";

// Overview タブの中、統計情報の上に配置
<CreativeViewer
  imageUrl={adData.image_url || adData.imageUrl}
  videoUrl={adData.video_url || adData.videoUrl}
  snapshotUrl={adData.snapshot_url || adData.snapshotUrl}
  thumbnailUrl={adData.thumbnail_url || adData.thumbnailUrl}
  creativeType={adData.creative_type || adData.creativeType}
/>
```

APIレスポンスのフィールド名に注意:
- バックエンドは snake_case (`image_url`, `video_url`)
- フロントエンドのスキーマが camelCase の場合がある
- 両方を `||` で受ける

### 4. APIデータ確認
`GET /api/v1/ads/{id}` のレスポンスで使えるフィールド:
```json
{
  "id": 11,
  "thumbnail_url": "https://scontent...",
  "image_url": "https://scontent...",
  "video_url": null,
  "snapshot_url": "https://www.facebook.com/ads/archive/render_ad/...",
  "creative_type": "unknown"
}
```

### 5. 検証
1. `npm run dev` でフロントエンド起動
2. ブラウザで http://localhost:3000 にアクセス
3. 広告一覧から任意の広告をクリック
4. モーダルに画像またはプレースホルダーが表示されること
5. 画像クリックで拡大表示が動作すること

## 注意事項
- `next/image` は外部URLのドメインホワイトリストが必要 → 通常の `<img>` タグを使う
- Facebook CDN URLは長い（200文字超）ので省略表示はしない
- 動画URLが外部CDNの場合、CORSの問題がありうる → `crossOrigin="anonymous"` を試す
- iframeでのFacebook埋め込みは X-Frame-Options で拒否される → 使わない
