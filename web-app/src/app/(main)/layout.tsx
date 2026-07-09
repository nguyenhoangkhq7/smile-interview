import type { Metadata } from 'next';
import Navbar from '@/components/layout/Navbar/Navbar';
import Footer from '@/components/layout/Footer/Footer';

export const metadata: Metadata = {
  title: 'Smile Interview — Phỏng Vấn Giả Lập Bằng AI',
  description:
    'Nền tảng luyện tập phỏng vấn AI thông minh. Tải CV, chọn JD và bắt đầu phỏng vấn thực tế với trợ lý AI giọng nói tự nhiên.',
  keywords: ['AI phỏng vấn', 'luyện tập phỏng vấn', 'CV', 'mock interview', 'AI interview'],
};

/**
 * Layout for all main app routes (home, login, register, interview, etc.)
 * Includes the shared Navbar and Footer.
 * Admin routes (/admin/**) use a completely separate layout without Navbar/Footer.
 */
export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <Navbar />
      <main style={{ flex: 1 }}>
        {children}
      </main>
      <Footer />
    </>
  );
}
