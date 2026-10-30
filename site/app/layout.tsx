import type { Metadata } from "next";
import "./globals.css";

const siteTitle = "DataPaper · 科研文献数据库";
const siteDescription =
  "从研究问题出发，检索数据论文、浏览摘要、比较候选并导出研究清单。";

export async function generateMetadata(): Promise<Metadata> {
  const origin =
    process.env.SITE_ORIGIN || "http://localhost:3000";

  return {
    title: siteTitle,
    description: siteDescription,
    icons: {
      icon: "/favicon.svg",
      shortcut: "/favicon.svg",
    },
    openGraph: {
      title: siteTitle,
      description: siteDescription,
      images: [`${origin}/og.png`],
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: siteTitle,
      description: siteDescription,
      images: [`${origin}/og.png`],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
