import type { Metadata } from 'next';
import localFont from 'next/font/local';
import { ThemeProvider } from 'next-themes';
import '../globals.css';
import 'katex/dist/katex.min.css';
import { cn } from "@/lib/utils";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import AuthSessionMonitor from '@/components/auth/AuthSessionMonitor';

const atlassianSans = localFont({
  src: './fonts/Atlassian-Sans.ttf',
  variable: '--font-atlassian-sans',
  weight: '100 900',
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" suppressHydrationWarning className={cn("font-sans", atlassianSans.variable)}>
      <body className="flex min-h-screen flex-col font-sans bg-background">
        <ThemeProvider attribute="class" defaultTheme="light" storageKey="smile-interview-theme" enableSystem enableColorScheme={false}>
          <TooltipProvider>
            <AuthSessionMonitor />
            {children}
            <Toaster position="top-center" richColors />
          </TooltipProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
