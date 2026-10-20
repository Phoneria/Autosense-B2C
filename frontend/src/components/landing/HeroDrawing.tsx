// Hero arka planı: markasız bir sedanın teknik yan görünüş çizimi (ölçü çizgileriyle, rakamsız).
// Dekoratiftir (aria-hidden); anlamı hero metni taşır. Logo, plaka, model adı ve fiyat içermez.

const WHEELS = [196, 626];
const SPOKES = Array.from({ length: 10 }, (_, i) => i * 36);

export default function HeroDrawing() {
  return (
    <svg viewBox="0 40 800 330" className="ld-blueprint" aria-hidden="true" focusable="false">
      {/* Merkez ve yardımcı çizgiler */}
      <g className="bp-guide">
        <line x1="20" y1="286" x2="780" y2="286" />
        {WHEELS.map((cx) => <line key={cx} x1={cx} y1="60" x2={cx} y2="320" />)}
      </g>

      <ellipse cx="410" cy="290" rx="340" ry="8" className="bp-shadow" />

      <g className="bp-car">
        {/* Gövde */}
        <path
          pathLength={1}
          className="bp-line bp-body"
          d="M86 236 C74 234 68 226 68 214 L70 188 C71 176 78 168 92 164 L146 152
             C178 146 206 140 232 134 C262 112 292 94 330 88 C380 81 440 81 486 86
             C520 90 548 102 576 124 L600 140 C640 145 690 151 720 160 C740 166 750 176 752 190
             L754 214 C754 226 746 234 734 236 L684 236
             A58 58 0 0 0 568 236 L254 236 A58 58 0 0 0 138 236 Z"
        />
        {/* Alt gövde gölgesi (karakter çizgisinin altı) */}
        <path
          className="bp-lower"
          d="M74 200 C260 192 560 192 752 202 L754 214 C754 226 746 234 734 236 L684 236
             A58 58 0 0 0 568 236 L254 236 A58 58 0 0 0 138 236 L86 236 C74 234 68 226 68 214 Z"
        />
        {/* Cam alanı ve yansıma */}
        <path pathLength={1} className="bp-line bp-glass" d="M248 136 C276 114 302 100 334 96 C378 90 432 90 474 94 C506 98 530 108 556 128 L566 138 Z" />
        <path className="bp-glare" d="M300 130 L344 100 L366 100 L322 132 Z M430 132 L452 96 L466 96 L444 132 Z" />
        {/* Kapı, direk ve hat çizgileri */}
        <path pathLength={1} className="bp-line bp-detail" d="M412 92 L408 138 M408 138 L404 232 M540 140 L536 232 M262 140 L268 232" />
        <path pathLength={1} className="bp-line bp-detail" d="M150 160 C300 146 520 146 712 162" />
        <path pathLength={1} className="bp-line bp-faint" d="M74 200 C260 192 560 192 752 202" />
        {/* Ayna, kollar, farlar, stop */}
        <path pathLength={1} className="bp-line bp-detail" d="M566 140 L590 134 L596 146 L572 148 Z" />
        <path pathLength={1} className="bp-line bp-detail" d="M352 166 L378 166 M484 166 L510 166" />
        <path pathLength={1} className="bp-line bp-detail bp-lamp" d="M704 168 C722 170 738 176 746 186 L716 184 C708 180 704 174 704 168 Z" />
        <path pathLength={1} className="bp-line bp-detail bp-lamp-rear" d="M74 178 L96 174 L98 192 L72 196 Z" />

        {WHEELS.map((cx) => (
          <g key={cx} className="bp-wheel">
            <circle cx={cx} cy={236} r={50} className="bp-tyre" />
            <circle cx={cx} cy={236} r={37} className="bp-rim" />
            <circle cx={cx} cy={236} r={27} className="bp-disc" />
            {SPOKES.map((a) => {
              const r = (a * Math.PI) / 180;
              return (
                <line key={a} className="bp-spoke"
                  x1={cx + Math.cos(r) * 9} y1={236 + Math.sin(r) * 9}
                  x2={cx + Math.cos(r) * 35} y2={236 + Math.sin(r) * 35} />
              );
            })}
            <circle cx={cx} cy={236} r={8} className="bp-hub" />
          </g>
        ))}
      </g>

      {/* Ölçü çizgileri (rakamsız) */}
      <g className="bp-dim">
        <line x1="68" y1="330" x2="754" y2="330" />
        <line x1="68" y1="320" x2="68" y2="340" />
        <line x1="754" y1="320" x2="754" y2="340" />
        <line x1="196" y1="310" x2="626" y2="310" />
        <line x1="196" y1="302" x2="196" y2="318" />
        <line x1="626" y1="302" x2="626" y2="318" />
        <line x1="784" y1="84" x2="784" y2="286" />
        <line x1="776" y1="84" x2="792" y2="84" />
        <line x1="776" y1="286" x2="792" y2="286" />
      </g>
    </svg>
  );
}
