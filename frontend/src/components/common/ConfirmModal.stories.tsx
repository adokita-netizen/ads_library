import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import ConfirmModal from "./ConfirmModal";

const meta: Meta<typeof ConfirmModal> = {
  title: "Common/ConfirmModal",
  component: ConfirmModal,
  tags: ["autodocs"],
  args: {
    title: "削除の確認",
    message: "この操作は元に戻せません。削除してよろしいですか？",
    confirmLabel: "削除する",
    cancelLabel: "キャンセル",
    onConfirm: () => {},
    onCancel: () => {},
  },
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Info: Story = {
  args: {
    variant: "info",
  },
};

export const Warning: Story = {
  args: {
    variant: "warning",
  },
};

export const Danger: Story = {
  args: {
    variant: "danger",
  },
};