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
    <html lang="ja">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
