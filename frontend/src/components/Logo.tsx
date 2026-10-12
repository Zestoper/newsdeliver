// NewsDeliver 로고 (기존 템플릿과 같은 모양)
export function LogoMark({ size = 34, bg = '#c00', border }: { size?: number; bg?: string; border?: string }) {
  const icon = Math.round(size * 0.59)
  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: size, height: size, background: bg, borderRadius: Math.round(size * 0.23), flexShrink: 0,
        border,
      }}
    >
      <svg width={icon} height={icon} viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <rect x="3" y="4" width="14" height="2" rx="1" fill="white" />
        <rect x="3" y="9" width="14" height="2" rx="1" fill="white" />
        <rect x="3" y="14" width="9" height="2" rx="1" fill="white" />
      </svg>
    </span>
  )
}
