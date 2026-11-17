import Image from 'next/image';

interface BrandLoadingProps {
  label: string;
  description?: string;
  className?: string;
}

export function BrandLoading({ label, description, className = '' }: BrandLoadingProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className={`flex min-h-64 flex-col items-center justify-center gap-3 rounded-2xl border border-border bg-card p-8 text-center shadow-sm ${className}`}
    >
      <picture>
        <source srcSet="/logo.png" media="(prefers-reduced-motion: reduce)" />
        <Image
          src="/media/logo_assembly_transparent.webp"
          alt=""
          aria-hidden="true"
          width={128}
          height={128}
          unoptimized
          className="size-32 object-contain"
        />
      </picture>
      <p className="font-semibold text-foreground">{label}</p>
      {description && <p className="max-w-md text-sm text-muted-foreground">{description}</p>}
    </div>
  );
}
