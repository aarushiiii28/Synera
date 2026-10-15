/** Static fallback: the same NASA day texture, cropped to a lit disc. Used while the WebGL globe loads, for reduced motion, or without WebGL. */
export function EarthStatic({ className = '' }: { className?: string }) {
  return (
    <div className={`relative rounded-full overflow-hidden ${className}`} aria-hidden style={{
      aspectRatio: '1', backgroundImage: 'url(/textures/earth_atmos_2048.jpg)', backgroundSize: '260% 100%', backgroundPosition: '62% 50%',
      boxShadow: '0 0 90px -10px rgba(22,181,255,.55), inset -50px -20px 90px 20px rgba(2,6,13,.92)',
    }}>
      <div className="absolute inset-0" style={{ background: 'radial-gradient(circle at 78% 30%, rgba(255,210,150,.35), transparent 40%)' }} />
    </div>
  );
}
