# B-R2-6: Notification Center (B42 Phase 2)
# 優先度: P2 | 前提: C-R2-2 (通知API) | ブロック: なし

## 目的
ヘッダーに通知ベルアイコンを配置し、通知一覧を表示する。

## 対象ファイル
- 新規: `frontend/src/components/common/NotificationCenter.tsx`
- 修正: `frontend/src/app/page.tsx` (ヘッダーに通知ベルを追加)

## 実装

### NotificationCenter.tsx
```tsx
interface Notification {
  id: number;
  type: 'alert' | 'new_ad' | 'analysis_complete' | 'system';
  title: string;
  body: string;
  read: boolean;
  created_at: string;
  ad_id?: number;
  action_url?: string;
}

// API: GET /api/v1/rankings/notifications?page=1&unread_only=false
// フォールバック: APIが無い場合はローカルストレージのトースト履歴を表示

export default function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // ポーリング (60秒ごと)
  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await fetchApi('/rankings/notifications?limit=20');
        setNotifications(res.notifications || []);
        setUnreadCount(res.unread_count || 0);
      } catch {
        // フォールバック: ローカルストレージからトースト履歴を読む
        const local = JSON.parse(localStorage.getItem('vaap-toast-history') || '[]');
        setNotifications(local.slice(0, 20));
        setUnreadCount(local.filter((n: any) => !n.read).length);
      }
    };
    fetch();
    const interval = setInterval(fetch, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative">
      {/* ベルアイコン + 未読バッジ */}
      <button onClick={() => setOpen(!open)} className="relative p-2">
        <BellIcon className="w-5 h-5 text-gray-600 dark:text-gray-300" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* ドロップダウン通知一覧 */}
      {open && (
        <div className="absolute right-0 top-10 w-80 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 z-50 max-h-96 overflow-y-auto">
          <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700">
            <span className="text-[13px] font-medium">Notifications</span>
            <button onClick={markAllRead} className="text-[11px] text-blue-500 hover:underline">
              Mark all read
            </button>
          </div>

          {notifications.length === 0 ? (
            <div className="p-6 text-center text-gray-400 text-[12px]">
              No notifications
            </div>
          ) : (
            notifications.map(n => (
              <NotificationItem key={n.id} notification={n} onRead={markRead} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
```

### 通知タイプ別アイコン/色
```
alert:             赤 bell   — アラートルール発火
new_ad:            緑 plus   — 新しいHIT広告検出
analysis_complete: 青 check  — 分析完了
system:            灰 info   — システム通知
```

### 既読API連携
```tsx
const markRead = async (id: number) => {
  try {
    await fetchApi(`/rankings/notifications/${id}/read`, { method: 'PUT' });
  } catch {
    // フォールバック: ローカルで既読マーク
  }
  setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
  setUnreadCount(prev => Math.max(0, prev - 1));
};

const markAllRead = async () => {
  try {
    await fetchApi('/rankings/notifications/read-all', { method: 'PUT' });
  } catch {}
  setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  setUnreadCount(0);
};
```

### page.tsx 統合
```tsx
// ヘッダー右端に ThemeToggle と並べて配置
<div className="flex items-center gap-2">
  <NotificationCenter />
  <ThemeToggle theme={theme} onToggle={toggleTheme} />
</div>
```

## 完了条件
- [ ] 通知ベルアイコンがヘッダーに表示される
- [ ] 未読バッジが表示される
- [ ] クリックでドロップダウンが開く
- [ ] 通知一覧が表示される
- [ ] 既読マークが動作する
- [ ] APIが無い場合のフォールバックが動作する
- [ ] ビルド成功
- [ ] status.md に記録
