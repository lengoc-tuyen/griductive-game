// Deterministic illustrated SVG avatar generator (Knotwise Griductive style)

(function (global) {
  const SKIN_TONES = ["#F9D8C0", "#F1C29B", "#E2A77D", "#C88459", "#9A6040", "#73422B"];
  const HAIR_COLORS = ["#26201D", "#4A2F21", "#7C4A27", "#C6863F", "#B54A2B", "#4B5563", "#D6A85A"];
  const SHIRT_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#14B8A6", "#6366F1", "#D97706", "#0EA5E9"];
  const BG_TINTS = ["#EFE8DA", "#E6EFEA", "#F4E7E4", "#E6ECF5", "#F3EEDB", "#ECE6F4"];

  function hashString(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function renderHair(style, color) {
    switch (style) {
      case 0: // Classic parted
        return `
          <path d="M18 33 C18 16, 46 16, 46 33 C43 26, 36 23, 28 24 C23 25, 20 28, 18 33 Z" fill="${color}"/>
          <path d="M21 22 C28 17, 42 18, 45 28" stroke="${color}" stroke-width="3" fill="none" stroke-linecap="round"/>
        `;
      case 1: // Top bun
        return `
          <circle cx="32" cy="14" r="6.5" fill="${color}"/>
          <path d="M18 34 C18 17, 46 17, 46 34 C42 25, 22 25, 18 34 Z" fill="${color}"/>
        `;
      case 2: // Bob / long side hair
        return `
          <path d="M16 39 C15 17, 49 17, 48 39 L45 45 L42 36 C40 26, 24 26, 22 36 L19 45 Z" fill="${color}"/>
        `;
      case 3: // Curly / afro puff
        return `
          <circle cx="22" cy="24" r="7" fill="${color}"/>
          <circle cx="32" cy="19" r="8" fill="${color}"/>
          <circle cx="42" cy="24" r="7" fill="${color}"/>
          <circle cx="19" cy="31" r="5" fill="${color}"/>
          <circle cx="45" cy="31" r="5" fill="${color}"/>
        `;
      case 4: // Spiky / textured short
        return `
          <path d="M18 32 L19 22 L24 24 L28 16 L33 22 L38 17 L41 24 L45 22 L46 32 C42 26, 22 26, 18 32 Z" fill="${color}"/>
        `;
      default: // Side swept long
        return `
          <path d="M17 42 C16 16, 48 16, 47 42 L43 44 C42 32, 41 26, 32 25 C25 25, 21 31, 20 44 Z" fill="${color}"/>
        `;
    }
  }

  function createAvatarSVG(name, sizeClass = "") {
    const safeName = String(name || "?");
    const h = hashString(safeName);
    const skin = SKIN_TONES[h % SKIN_TONES.length];
    const hair = HAIR_COLORS[(h >>> 4) % HAIR_COLORS.length];
    const shirt = SHIRT_COLORS[(h >>> 8) % SHIRT_COLORS.length];
    const bg = BG_TINTS[(h >>> 12) % BG_TINTS.length];
    const hairStyle = (h >>> 16) % 6;
    const hasGlasses = ((h >>> 20) % 5) === 0;
    const smileStyle = (h >>> 23) % 3;

    let mouth = `<path d="M28 40 Q32 43.5 36 40" stroke="#262420" stroke-width="1.8" fill="none" stroke-linecap="round"/>`;
    if (smileStyle === 1) {
      mouth = `<path d="M29 40.5 Q32 42 35 40.5" stroke="#262420" stroke-width="1.8" fill="none" stroke-linecap="round"/>`;
    } else if (smileStyle === 2) {
      mouth = `<path d="M28.5 39.5 Q32 44 35.5 39.5 Z" fill="#FFFFFF" stroke="#262420" stroke-width="1.4" stroke-linejoin="round"/>`;
    }

    const glasses = hasGlasses
      ? `
        <rect x="22.5" y="31" width="7.5" height="5.5" rx="2" fill="rgba(255,255,255,0.28)" stroke="#262420" stroke-width="1.4"/>
        <rect x="34" y="31" width="7.5" height="5.5" rx="2" fill="rgba(255,255,255,0.28)" stroke="#262420" stroke-width="1.4"/>
        <line x1="30" y1="33.5" x2="34" y2="33.5" stroke="#262420" stroke-width="1.4"/>
      `
      : "";

    const backHair =
      hairStyle === 2 || hairStyle === 5
        ? `<ellipse cx="32" cy="35" rx="16" ry="15" fill="${hair}"/>`
        : "";

    return `
      <svg class="avatar-svg ${sizeClass}" viewBox="0 0 64 64" aria-hidden="true">
        <defs>
          <clipPath id="clip-${h}">
            <circle cx="32" cy="32" r="30"/>
          </clipPath>
        </defs>
        <circle cx="32" cy="32" r="30" fill="${bg}"/>
        <g clip-path="url(#clip-${h})">
          ${backHair}
          <!-- Shoulders / Shirt -->
          <path d="M12 64 C13 50, 22 46, 32 46 C42 46, 51 50, 52 64 Z" fill="${shirt}" stroke="#262420" stroke-width="1.8"/>
          <!-- Collar detail -->
          <path d="M27 46 L32 52 L37 46" fill="none" stroke="rgba(255,255,255,0.65)" stroke-width="1.6" stroke-linejoin="round"/>
          <!-- Neck -->
          <rect x="28.5" y="42" width="7" height="7" rx="3" fill="${skin}"/>
          <!-- Ears -->
          <circle cx="19" cy="34.5" r="3.2" fill="${skin}"/>
          <circle cx="45" cy="34.5" r="3.2" fill="${skin}"/>
          <!-- Head -->
          <rect x="20" y="21" width="24" height="24.5" rx="12" fill="${skin}" stroke="#262420" stroke-width="1.5"/>
          <!-- Cheeks -->
          <circle cx="24.5" cy="37.5" r="2" fill="#F48A8A" opacity="0.32"/>
          <circle cx="39.5" cy="37.5" r="2" fill="#F48A8A" opacity="0.32"/>
          <!-- Eyes -->
          <circle cx="26.5" cy="33.5" r="1.7" fill="#262420"/>
          <circle cx="37.5" cy="33.5" r="1.7" fill="#262420"/>
          <!-- Eyebrows -->
          <path d="M24 29.8 Q26.5 28.6 29 29.8" stroke="${hair}" stroke-width="1.4" fill="none" stroke-linecap="round"/>
          <path d="M35 29.8 Q37.5 28.6 40 29.8" stroke="${hair}" stroke-width="1.4" fill="none" stroke-linecap="round"/>
          ${mouth}
          ${glasses}
          ${renderHair(hairStyle, hair)}
        </g>
        <circle cx="32" cy="32" r="30" fill="none" stroke="#262420" stroke-width="2"/>
      </svg>
    `;
  }

  global.createAvatarSVG = createAvatarSVG;
})(window);
