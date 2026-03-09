# B-R2-1: Dark Mode & Responsive Enhancement (B29)
# 優先度: P1 | 前提: なし | ブロック: なし

## 目的
主要5画面にダークモードを追加し、テーマ切替を実装する。

## 対象ファイル
- `frontend/src/app/layout.tsx` (修正)
- `frontend/src/app/page.tsx` (修正)
- `frontend/src/components/common/Sidebar.tsx` (修正)
- `frontend/src/components/dashboard/ProRankingView.tsx` (修正)
- `frontend/src/components/dashboard/ProRankingTable.tsx` (修正)
- `frontend/src/components/dashboard/HitAdAnalysisView.tsx` (修正)
- `frontend/src/components/dashboard/AdDetailModal.tsx` (修正)
- 新規: `frontend/src/components/common/ThemeToggle.tsx`
- 新規: `frontend/src/hooks/useTheme.ts`

## 実装

### Step 1: Tailwind dark mode 設定
```js
// tailwind.config.js に追加（既存の場合は確認のみ）
module.exports = {
  darkMode: 'class',  // class ベースの dark mode
  // ...
}
```

### Step 2: useTheme フック
```typescript
// frontend/src/hooks/useTheme.ts
import { useState, useEffect } from 'react';

export function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    const saved = localStorage.getItem('vaap-theme') as 'light' | 'dark' | null;
    const preferred = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    setTheme(preferred);
    document.documentElement.classList.toggle('dark', preferred === 'dark');
  }, []);

  const toggleTheme = () => {
    const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next);
    localStorage.setItem('vaap-theme', next);
    document.documentElement.classList.toggle('dark', next === 'dark');
  };

  return { theme, toggleTheme };
}
```

### Step 3: ThemeToggle コンポーネント
```tsx
// frontend/src/components/common/ThemeToggle.tsx
interface ThemeToggleProps {
  theme: 'light' | 'dark';
  onToggle: () => void;
}

export default function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  return (
    <button
      onClick={onToggle}
      className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
    >
      {theme === 'light' ? (
        // Moon icon (SVG inline)
        <svg className="w-5 h-5 text-gray-600" ...>...</svg>
      ) : (
        // Sun icon (SVG inline)
        <svg className="w-5 h-5 text-yellow-400" ...>...</svg>
      )}
    </button>
  );
}
```

### Step 4: 主要コンポーネントに dark: クラス追加

#### 共通パターン
```
bg-white         → bg-white dark:bg-gray-900
bg-gray-50       → bg-gray-50 dark:bg-gray-800
text-gray-900    → text-gray-900 dark:text-gray-100
text-gray-500    → text-gray-500 dark:text-gray-400
border-gray-200  → border-gray-200 dark:border-gray-700
hover:bg-gray-50 → hover:bg-gray-50 dark:hover:bg-gray-700
```

#### 対象コンポーネント (各ファイルの bg-white, text-gray-900 等を置換)
1. **Sidebar.tsx**: サイドバー背景 + ナビアイテム
2. **page.tsx**: メインエリア背景
3. **ProRankingView.tsx**: ヘッダー + フィルター + ジャンルサイドバー
4. **ProRankingTable.tsx**: テーブルヘッダー + 行 + ホバー
5. **HitAdAnalysisView.tsx**: カード + テーブル + フィルター
6. **AdDetailModal.tsx**: モーダル背景 + テキスト + メトリクスカード

### Step 5: layout.tsx に ThemeProvider 統合
```tsx
// page.tsx のヘッダーに ThemeToggle を配置
import { useTheme } from '@/hooks/useTheme';
import ThemeToggle from '@/components/common/ThemeToggle';

// ... inside component
const { theme, toggleTheme } = useTheme();

// ヘッダー右端に配置
<ThemeToggle theme={theme} onToggle={toggleTheme} />
```

## ビルド確認
```bash
cd C:/Users/ishit/ads_library/frontend
npx next build --no-lint
```

## 完了条件
- [ ] ダークモードトグルがヘッダーに表示される
- [ ] テーマが localStorage に永続化される
- [ ] 主要5画面でダークモードが正しく表示される
- [ ] テキストのコントラスト比が十分（暗い背景に明るいテキスト）
- [ ] ビルドが成功する
- [ ] status.md に記録
