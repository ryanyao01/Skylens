/**
 * Raw color values. Components should use the semantic `colors` below instead,
 * so a color can be changed by role ("secondary text") rather than by value.
 *
 * Neutral steps follow Tailwind's neutral scale where the values match;
 * 100, 600 and 700 are Skylens-specific.
 */
export const palette = {
  white: "#FFFFFF",
  black: "#000000",

  neutral100: "#E6E6E6",
  neutral400: "#A1A1A1",
  neutral500: "#737373",
  neutral600: "#474747",
  neutral700: "#3A3A3A",
  neutral800: "#262626",
  neutral900: "#171717",
  neutral950: "#0A0A0A",

  cyan: "#00D3F2",
  blue: "#426CEB",
  green: "#39FF70",
  amber: "#F59E0B",
  red: "#6E1414",

  // Translucent variants, named <color>A<opacity %>
  whiteA10: "rgba(255, 255, 255, 0.1)",
  whiteA20: "rgba(255, 255, 255, 0.2)",
  whiteA30: "rgba(255, 255, 255, 0.3)",
  whiteA50: "rgba(255, 255, 255, 0.5)",
  whiteA80: "rgba(255, 255, 255, 0.8)",
  whiteA90: "rgba(255, 255, 255, 0.9)",
  blackA40: "rgba(0, 0, 0, 0.4)",
  blackA50: "rgba(0, 0, 0, 0.5)",
  blackA65: "rgba(0, 0, 0, 0.65)",
  neutral900A0: "rgba(23, 23, 23, 0)",
  neutral900A80: "rgba(23, 23, 23, 0.8)",
  blueA20: "rgba(66, 108, 235, 0.2)",
} as const;

export const colors = {
  background: {
    base: palette.neutral950,
    camera: palette.black,
  },

  surface: {
    // Cards, dialogs, tab bar
    base: palette.neutral900,
    // Floating controls over the map
    translucent: palette.neutral900A80,
    // Same hue as `base` at 0% so gradients into it don't turn gray midway
    transparent: palette.neutral900A0,
    // Wells nested inside a surface, e.g. stat boxes
    inset: palette.neutral950,
  },

  border: {
    subtle: palette.neutral800,
    strong: palette.neutral700,
  },

  // Used for both text and icons
  text: {
    primary: palette.white,
    secondary: palette.neutral400,
    tertiary: palette.neutral500,
    // On light fills
    inverse: palette.neutral950,
    // Flight data readouts and highlights
    accent: palette.cyan,
  },

  // Translucent layers over photos, the camera feed and the map
  overlay: {
    scrim: palette.blackA65,
    fill: palette.blackA40,
    fillStrong: palette.blackA50,
    border: palette.whiteA10,
    borderStrong: palette.whiteA30,
    text: palette.whiteA80,
    icon: palette.whiteA50,
  },

  button: {
    primary: palette.white,
    primaryPressed: palette.neutral100,
    primaryText: palette.black,
    secondary: palette.neutral800,
    secondaryPressed: palette.neutral600,
  },

  shutter: {
    fill: palette.whiteA20,
    border: palette.white,
    core: palette.white,
    fillPressed: palette.blueA20,
    borderPressed: palette.blue,
    corePressed: palette.blue,
  },

  tabBar: {
    background: palette.neutral900,
    border: palette.neutral800,
    active: palette.white,
    inactive: palette.neutral500,
    indicator: palette.white,
    // Selected icon drawn on top of the indicator pill
    activeIcon: palette.neutral900,
  },

  marker: {
    border: palette.whiteA90,
  },

  // Airport congestion score gradient, low (0) to high (100)
  congestion: {
    low: palette.green,
    moderate: palette.amber,
    high: palette.red,
    // A score of exactly 0 usually means missing data, not an empty airport
    noData: palette.neutral500,
  },

  shadow: palette.black,
} as const;
