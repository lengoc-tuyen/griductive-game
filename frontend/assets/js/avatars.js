// Deterministic SVG Avatar Generator for Griductive characters

(function () {
  const BG_COLORS = [
    "#E6DEC8", "#DCE8E2", "#E9DFD3", "#DDE4EE",
    "#EDE0D4", "#E2E6D5", "#EAE0E5", "#F0E5CE"
  ];

  const SKIN_TONES = [
    "#F8D9C2", "#F1C29B", "#E0A882", "#C68863",
    "#9E6544", "#70452C"
  ];

  const HAIR_COLORS = [
    "#262420", "#4A3222", "#6E4427", "#9C5B2E",
    "#C88A3B", "#5A5A60", "#8D3B32", "#344154"
  ];

  const SHIRT_COLORS = [
    "#4B7B70", "#C86D51", "#546E8A", "#B88B3E",
    "#7A648A", "#5F8052", "#9E525A", "#4A6B82"
  ];

  let clipCounter = 0;

  function hashString(str) {
    let h = 2166136261;
    const input = String(str || "Character");
    for (let i = 0; i < input.length; i++) {
      h ^= input.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function escapeXml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderHairBack(style, color) {
    if (style === 1) {
      return `<path d="M21 36 C20 55, 22 66, 26 70 L54 70 C58 66, 60 55, 59 36 Z" fill="${color}" stroke="#262420" stroke-width="2" />`;
    }
    if (style === 2) {
      return `<circle cx="24" cy="40" r="9" fill="${color}" stroke="#262420" stroke-width="2" />
              <circle cx="56" cy="40" r="9" fill="${color}" stroke="#262420" stroke-width="2" />`;
    }
    if (style === 3) {
      return `<circle cx="40" cy="14" r="8" fill="${color}" stroke="#262420" stroke-width="2" />`;
    }
    return "";
  }

  function renderHairFront(style, color) {
    switch (style) {
      case 0:
        return `<path d="M23 36 C23 21, 57 21, 57 36 C54 29, 44 27, 35 30 C29 32, 25 34, 23 36 Z" fill="${color}" stroke="#262420" stroke-width="2" stroke-linejoin="round" />`;
      case 1:
        return `<path d="M23 37 C23 20, 57 20, 57 37 C52 30, 44 29, 40 33 C36 29, 28 30, 23 37 Z" fill="${color}" stroke="#262420" stroke-width="2" stroke-linejoin="round" />`;
      case 2:
        return `<path d="M22 36 C21 20, 59 20, 58 36 C52 28, 28 28, 22 36 Z" fill="${color}" stroke="#262420" stroke-width="2" stroke-linejoin="round" />`;
      case 3:
        return `<path d="M24 35 C25 21, 55 21, 56 35 C50 28, 30 28, 24 35 Z" fill="${color}" stroke="#262420" stroke-width="2" stroke-linejoin="round" />`;
      default:
        return `<path d="M23 36 C23 22, 57 22, 57 36 L52 29 L45 32 L40 27 L34 32 L28 29 Z" fill="${color}" stroke="#262420" stroke-width="2" stroke-linejoin="round" />`;
    }
  }

  function createAvatarSVG(name, profession = "", size = 56) {
    const seed = hashString(`${name}|${profession}`);
    const bg = BG_COLORS[seed % BG_COLORS.length];
    const skin = SKIN_TONES[(seed >>> 3) % SKIN_TONES.length];
    const hair = HAIR_COLORS[(seed >>> 6) % HAIR_COLORS.length];
    const shirt = SHIRT_COLORS[(seed >>> 9) % SHIRT_COLORS.length];
    const hairStyle = (seed >>> 12) % 5;
    const hasGlasses = ((seed >>> 15) % 4) === 0;
    const smileType = (seed >>> 17) % 3;

    clipCounter += 1;
    const clipId = `avatar-clip-${clipCounter}`;
    const label = escapeXml(`${name}${profession ? " - " + profession : ""}`);

    const mouthMarkup =
      smileType === 0
        ? `<path d="M35 48 Q40 52 45 48" fill="none" stroke="#262420" stroke-width="2" stroke-linecap="round" />`
        : smileType === 1
        ? `<path d="M36 49 L44 49" fill="none" stroke="#262420" stroke-width="2" stroke-linecap="round" />`
        : `<path d="M35 48 Q40 51 45 48" fill="none" stroke="#262420" stroke-width="2" stroke-linecap="round" />`;

    const glassesMarkup = hasGlasses
      ? `<g stroke="#262420" stroke-width="1.8" fill="rgba(255,255,255,0.28)">
           <circle cx="34" cy="40" r="4.5" />
           <circle cx="46" cy="40" r="4.5" />
           <line x1="38.5" y1="40" x2="41.5" y2="40" />
         </g>`
      : "";

    return `
      <svg width="${size}" height="${size}" viewBox="0 0 80 80" role="img" aria-label="${label}" style="display:block;">
        <defs>
          <clipPath id="${clipId}">
            <circle cx="40" cy="40" r="37" />
          </clipPath>
        </defs>
        <circle cx="40" cy="40" r="37" fill="${bg}" />
        <g clip-path="url(#${clipId})">
          ${renderHairBack(hairStyle, hair)}
          <path d="M16 78 C18 61, 62 61, 64 78 Z" fill="${shirt}" stroke="#262420" stroke-width="2.2" />
          <rect x="35" y="51" width="10" height="11" rx="4" fill="${skin}" stroke="#262420" stroke-width="2" />
          <circle cx="24" cy="41" r="3.5" fill="${skin}" stroke="#262420" stroke-width="1.8" />
          <circle cx="56" cy="41" r="3.5" fill="${skin}" stroke="#262420" stroke-width="1.8" />
          <rect x="25" y="24" width="30" height="31" rx="14" fill="${skin}" stroke="#262420" stroke-width="2.2" />
          <circle cx="34" cy="40" r="2" fill="#262420" />
          <circle cx="46" cy="40" r="2" fill="#262420" />
          <path d="M31 36 Q34 34.5 37 36" fill="none" stroke="#262420" stroke-width="1.6" stroke-linecap="round" />
          <path d="M43 36 Q46 34.5 49 36" fill="none" stroke="#262420" stroke-width="1.6" stroke-linecap="round" />
          ${glassesMarkup}
          ${mouthMarkup}
          ${renderHairFront(hairStyle, hair)}
        </g>
        <circle cx="40" cy="40" r="37" fill="none" stroke="#262420" stroke-width="2.4" />
      </svg>
    `;
  }

  window.createAvatarSVG = createAvatarSVG;
})();