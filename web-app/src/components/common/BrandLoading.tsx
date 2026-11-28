import Image from 'next/image';

interface BrandLoadingProps {
  label: string;
  description?: string;
  className?: string;
  embedded?: boolean;
}

export function BrandLoading({ label, description, className = '', embedded = false }: BrandLoadingProps) {
  const layout = embedded ? 'py-3 text-sm' : 'min-h-64 rounded-2xl border border-border bg-card p-8 shadow-sm';

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className={`flex flex-col items-center justify-center gap-3 text-center ${layout} ${className}`}
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
          className={embedded ? 'size-24 object-contain' : 'size-32 object-contain'}
        />
      </picture>
      <p className="font-semibold text-foreground">{label}</p>
      {description && <p className="max-w-md text-sm text-muted-foreground">{description}</p>}
    </div>
  );
}
