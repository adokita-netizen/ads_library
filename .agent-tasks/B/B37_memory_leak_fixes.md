# B37: メモリリーク修正

## 問題
- `ProductDetailModal.tsx`: setTimeout の cleanup がない → コンポーネントアンマウント後に state 更新試行
- `AdLibrary.tsx` / `CrawlModal`: setInterval ポーリングのクリーンアップ不備 → タブ切替やモーダル閉後もリクエスト継続
- useEffect 内の非同期処理で unmounted コンポーネントへの setState

## 対象ファイル
- `frontend/src/components/ProductDetailModal.tsx`
- `frontend/src/components/AdLibrary.tsx`
- `frontend/src/components/CrawlModal.tsx`（存在する場合）

## 修正

### 1. setTimeout / setInterval の cleanup
```tsx
// Before (リーク)
useEffect(() => {
  const timer = setTimeout(() => setSomething(true), 3000);
  // cleanup なし
}, []);

// After
useEffect(() => {
  const timer = setTimeout(() => setSomething(true), 3000);
  return () => clearTimeout(timer);
}, []);
```

### 2. ポーリングの cleanup
```tsx
useEffect(() => {
  if (!isPolling) return;
  const interval = setInterval(async () => {
    const result = await fetchStatus();
    if (result.done) {
      clearInterval(interval);
      setIsPolling(false);
    }
  }, 5000);
  return () => clearInterval(interval);
}, [isPolling]);
```

### 3. アンマウント後の setState 防止
```tsx
useEffect(() => {
  let cancelled = false;
  async function load() {
    const data = await fetchData();
    if (!cancelled) setData(data);
  }
  load();
  return () => { cancelled = true; };
}, [id]);
```

## 制約
- 各コンポーネントの既存UIは変更しない
- cleanup 追加のみ
