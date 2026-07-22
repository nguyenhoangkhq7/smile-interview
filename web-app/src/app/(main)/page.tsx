import { HeroSection } from '@/components/features/home/HeroSection';
import { StatsSection } from '@/components/features/home/StatsSection';
import { StepsSection } from '@/components/features/home/StepsSection';
import { FeaturesSection } from '@/components/features/home/FeaturesSection';
import { CtaSection } from '@/components/features/home/CtaSection';

export default function HomePage() {
  return (
    <div>
      <HeroSection />
      <StatsSection />
      <StepsSection />
      <FeaturesSection />
      <CtaSection />
    </div>
  );
}
