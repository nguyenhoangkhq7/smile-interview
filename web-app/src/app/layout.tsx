import type { Metadata } from 'next';
import { Geist } from 'next/font/google';
import '../globals.css';
import { cn } from "@/lib/utils";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

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
    <html lang="vi" className={cn("font-sans", geist.variable)}>
      <body className="flex min-h-screen flex-col font-sans bg-background">
        <TooltipProvider>
          {children}
          <Toaster position="top-center" richColors />
        </TooltipProvider>
      </body>
    </html>
  );
}
