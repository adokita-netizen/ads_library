import type { Metadata } from "next";
import Providers from "@/components/common/Providers";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "VAAP - Video Ad Analysis AI Platform",
  description: "動画広告分析AIプラットフォーム",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja" suppressHydrationWarning>
      <body className="bg-[#f5f6fa] text-gray-900 dark:bg-gray-950 dark:text-gray-100">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
