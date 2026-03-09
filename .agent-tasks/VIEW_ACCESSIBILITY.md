# アクセシビリティ視点 — 全てのユーザーが使えるプロダクトに

## なぜアクセシビリティが重要か

- 日本のWebアクセシビリティ基準（JIS X 8341-3）対応
- 色覚多様性を持つユーザー（日本人男性の5%）
- キーボードのみでの操作（パワーユーザーにも有益）
- スクリーンリーダー対応（視覚障害ユーザー）
- 法的要件（障害者差別解消法 2024年改正）

---

## 現状の課題（推定）

### 色コントラスト

```
問題箇所:
  - HIT/大HIT のバッジ色が背景と区別しにくい可能性
  - 金色ハイライト行の文字が読みにくい可能性
  - ダークモード非対応（目の疲労）

基準:
  WCAG AA: コントラスト比 4.5:1（通常テキスト）
  WCAG AA: コントラスト比 3:1（大テキスト、UIコンポーネント）
```

### キーボードナビゲーション

```
問題箇所:
  - テーブル行のクリックがマウス前提
  - モーダルの閉じるボタンにフォーカスが移らない
  - サイドバーのTab順序が不明確
  - フィルター操作がキーボードで不可能

必要な対応:
  - 全インタラクティブ要素に tabindex
  - フォーカス表示（:focus-visible）
  - Esc でモーダル閉じる
  - Enter/Space でボタン/リンク操作
```

### スクリーンリーダー

```
問題箇所:
  - 画像/サムネイルに alt テキストがない
  - テーブルに適切な <th> scope がない
  - チャートの数値がテキストとして読めない
  - 動的コンテンツの変更が通知されない

必要な対応:
  - aria-label, aria-describedby の追加
  - aria-live="polite" でテーブル更新通知
  - チャートにデータテーブルの代替テキスト
```

---

## WCAG 2.1 AA 準拠チェックリスト

### 知覚可能

```
□ テキストのコントラスト比 4.5:1 以上
□ 画像に代替テキスト
□ 色だけで情報を伝えない（アイコンも併用）
  × HIT → 色のみ
  ○ HIT → 🎯 バッジ + テキスト + 色
□ テキストのリサイズ 200% で情報欠落なし
□ メディアにキャプション/代替テキスト
```

### 操作可能

```
□ 全機能がキーボードで操作可能
□ フォーカス順序が論理的
□ フォーカスインジケーターが見える
□ 時間制限のあるコンテンツがない
□ 点滅するコンテンツがない（3回/秒以下）
□ ナビゲーションをスキップする手段がある
```

### 理解可能

```
□ ページの言語が指定されている（lang="ja"）
□ ラベルが入力フィールドに関連付けられている
□ エラーメッセージが明確
□ 一貫したナビゲーション
```

### 堅牢

```
□ 有効なHTML
□ コンポーネントに name, role, value がある
□ ステータスメッセージに aria-live がある
```

---

## コンポーネント別の改善

### テーブル（PRO DATABASE）

```html
<!-- 現在（推定） -->
<div class="table">
  <div class="row" onclick="...">
    <div class="cell">85</div>
    <div class="cell">美容液...</div>
  </div>
</div>

<!-- 改善後 -->
<table role="grid" aria-label="PRO DATABASE ランキング">
  <thead>
    <tr>
      <th scope="col" aria-sort="descending">
        <button>スコア ▼</button>
      </th>
      <th scope="col">タイトル</th>
    </tr>
  </thead>
  <tbody>
    <tr
      role="row"
      tabindex="0"
      aria-label="スコア85、美容液..."
      onKeyDown={handleRowKeyDown}
    >
      <td>85</td>
      <td>美容液...</td>
    </tr>
  </tbody>
</table>
```

### モーダル（AdDetailModal）

```typescript
// フォーカストラップ
function useFocusTrap(modalRef: RefObject<HTMLElement>) {
  useEffect(() => {
    const modal = modalRef.current;
    if (!modal) return;

    const focusableElements = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const first = focusableElements[0] as HTMLElement;
    const last = focusableElements[focusableElements.length - 1] as HTMLElement;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') closeModal();
      if (e.key === 'Tab') {
        if (e.shiftKey && document.activeElement === first) {
          last.focus();
          e.preventDefault();
        } else if (!e.shiftKey && document.activeElement === last) {
          first.focus();
          e.preventDefault();
        }
      }
    }

    modal.addEventListener('keydown', handleKeyDown);
    first.focus();
    return () => modal.removeEventListener('keydown', handleKeyDown);
  }, []);
}

// モーダルの aria 属性
<div
  role="dialog"
  aria-modal="true"
  aria-labelledby="modal-title"
  aria-describedby="modal-description"
>
  <h2 id="modal-title">広告詳細</h2>
  <p id="modal-description">広告ID: {adId} のスコアと詳細情報</p>
</div>
```

### チャート

```typescript
// チャートにアクセシブルな代替テキストを提供
<div role="img" aria-label="ジャンル別ヒット率: 美容 35%, 健康食品 28%, ダイエット 20%">
  <BarChart data={data} />
</div>

// さらにデータテーブルを sr-only で提供
<table className="sr-only">
  <caption>ジャンル別ヒット率</caption>
  <thead><tr><th>ジャンル</th><th>ヒット率</th></tr></thead>
  <tbody>
    <tr><td>美容</td><td>35%</td></tr>
    <tr><td>健康食品</td><td>28%</td></tr>
    <tr><td>ダイエット</td><td>20%</td></tr>
  </tbody>
</table>
```

### ヒットバッジ

```typescript
// 色だけに頼らない
// 現在（推定）
<span className="text-gold">HIT</span>

// 改善後
<span
  className="hit-badge"
  role="status"
  aria-label={`ヒットレベル: ${hitLevel}`}
>
  {hitLevel === '大HIT' && '🔥 '}
  {hitLevel === 'HIT' && '🎯 '}
  {hitLevel}
</span>
```

---

## キーボードショートカット

### グローバル

```
? → ショートカット一覧表示
/ → 検索バーにフォーカス
Esc → モーダル閉じる/検索バー解除
```

### テーブル

```
↑/↓ → 行選択
Enter → 選択行の詳細を開く
Esc → 選択解除
Home → 先頭行
End → 末尾行
```

### フィルター

```
f → フィルターパネルにフォーカス
r → フィルターリセット
```

---

## テスト方法

### 自動テスト

```bash
# axe-core でアクセシビリティ検証
npx @axe-core/cli http://localhost:3000

# Lighthouse アクセシビリティスコア
npx lighthouse http://localhost:3000 --only-categories=accessibility

# jest-axe（ユニットテスト）
import { axe, toHaveNoViolations } from 'jest-axe';
expect.extend(toHaveNoViolations);

it('テーブルにアクセシビリティ違反がない', async () => {
  const { container } = render(<ProRankingTable />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

### 手動テスト

```
1. Tab キーのみでフルナビゲーション
   → 全要素にアクセスできるか
   → フォーカスインジケーターが見えるか

2. スクリーンリーダー（NVDA / VoiceOver）
   → テーブルの読み上げ
   → モーダルの操作
   → 通知の読み上げ

3. ズーム 200%
   → レイアウトが崩れないか
   → テキストが切れないか

4. カラーコントラストチェッカー
   → Chrome DevTools → Rendering → Emulate vision deficiencies
```

---

## 実装優先度

```
[Phase 1: 低コスト・高インパクト]
  1. lang="ja" 追加
  2. alt テキスト追加（サムネイル、アイコン）
  3. :focus-visible スタイル追加
  4. Esc でモーダル閉じる
  5. コントラスト比の修正

[Phase 2: 構造改善]
  6. テーブルの <table> 化 + aria 属性
  7. フォーカストラップ（モーダル）
  8. キーボードナビゲーション
  9. aria-live でテーブル更新通知

[Phase 3: 高度な対応]
  10. チャートの代替テキスト/データテーブル
  11. キーボードショートカット
  12. スクリーンリーダーテスト
  13. アクセシビリティステートメント作成
```
