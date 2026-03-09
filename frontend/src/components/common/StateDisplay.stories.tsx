import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { EmptyState, ErrorState, FullPageLoader, LoadingSpinner } from "./StateDisplay";

const meta: Meta<typeof LoadingSpinner> = {
  title: "Common/StateDisplay",
  component: LoadingSpinner,
  tags: ["autodocs"],
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Spinner: Story = {
  args: {
    label: "読み込み中...",
    size: "md",
  },
};

export const FullLoader: Story = {
  render: () => (
    <div className="h-[280px] border border-gray-200 rounded-lg">
      <FullPageLoader label="データを取得しています" />
    </div>
  ),
};

export const EmptyWithAction: Story = {
  render: () => (
    <EmptyState
      icon="search"
      message="該当データが見つかりません"
      description="条件を変更して再検索してください"
      actionLabel="フィルターをリセット"
      onAction={() => {}}
    />
  ),
};

export const ErrorCompact: Story = {
  render: () => <ErrorState compact message="通信エラーが発生しました" onRetry={() => {}} />,
};