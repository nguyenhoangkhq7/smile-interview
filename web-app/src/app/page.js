import { DittoAvatarModule } from '@/components/DittoAvatarModule';
import styles from './page.module.css';

export const metadata = {
  title: 'Ditto — AI Interview Avatar',
  description:
    'Real-time 3D AI interview avatar powered by Next.js, Three.js, and WebSockets.',
};

export default function Home() {
  return (
    <main className={styles.main}>
      {/* ── Background ── */}
      <div className={styles.background} aria-hidden="true">
        <div className={styles.bgGlow1} />
        <div className={styles.bgGlow2} />
        <div className={styles.bgGrid} />
      </div>

      {/* ── Header ── */}
      <header className={styles.header}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>◈</span>
          <span className={styles.logoText}>Ditto</span>
          <span className={styles.logoBadge}>AI</span>
        </div>
        <p className={styles.tagline}>Your intelligent mock-interview companion</p>
      </header>

      {/* ── Avatar Stage ── */}
      <section className={styles.stage} aria-label="3D Avatar Stage">
        <div className={styles.avatarCard}>
          <DittoAvatarModule />
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className={styles.footer}>
        <p>Powered by Next.js · Three.js · WebSockets</p>
      </footer>
    </main>
  );
}
