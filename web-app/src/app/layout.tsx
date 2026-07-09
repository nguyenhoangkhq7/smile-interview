import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin', 'vietnamese'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    template: '%s — Smile Interview',
    default: 'Smile Interview — Phỏng Vấn Giả Lập Bằng AI',
  },
  description:
    'Nền tảng luyện tập phỏng vấn AI thông minh. Tải CV, chọn JD và bắt đầu phỏng vấn thực tế với trợ lý AI giọng nói tự nhiên.',
};

/**
 * Root layout — shared HTML shell for the ENTIRE application.
 *
 * This layout intentionally does NOT include <Navbar> or <Footer>.
 * Those are provided by nested route-group layouts:
 *   - (main)/layout.tsx  → public/user pages (Navbar + Footer)
 *   - admin/layout.tsx   → admin pages (dark sidebar, no Navbar/Footer)
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className={inter.variable}>
      <body
        style={{
          display: 'flex',
          minHeight: '100vh',
          flexDirection: 'column',
          backgroundColor: '#fdfbf7',
          fontFamily: 'var(--font-inter), system-ui, sans-serif',
        }}
      >
        {children}
      </body>
    </html>
  );
}
