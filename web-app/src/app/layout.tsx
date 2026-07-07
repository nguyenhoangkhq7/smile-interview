import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Navbar from '@/components/layout/Navbar/Navbar';
import Footer from '@/components/layout/Footer/Footer';

const inter = Inter({
  subsets: ['latin', 'vietnamese'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Smile Interview — Phỏng Vấn Giả Lập Bằng AI',
  description:
    'Nền tảng luyện tập phỏng vấn AI thông minh. Tải CV, chọn JD và bắt đầu phỏng vấn thực tế với trợ lý AI giọng nói tự nhiên.',
  keywords: ['AI phỏng vấn', 'luyện tập phỏng vấn', 'CV', 'mock interview', 'AI interview'],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className={inter.variable}>
      <body style={{ display: 'flex', minHeight: '100vh', flexDirection: 'column', backgroundColor: '#fdfbf7', fontFamily: 'var(--font-inter), system-ui, sans-serif' }}>
        <Navbar />
        <main style={{ flex: 1 }}>
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
