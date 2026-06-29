import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Ditto — AI Interview Avatar',
  description:
    'Real-time 3D AI interview avatar powered by Next.js, Three.js, and WebSockets.',
  keywords: ['AI', 'interview', 'avatar', '3D', 'WebSockets', 'lip-sync'],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
