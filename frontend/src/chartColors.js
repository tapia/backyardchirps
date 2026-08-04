export const CHART_COLORS = {
  tooltip: {
    background: '#252320',
    title: '#DAD6CE',
    body: '#F4F1EB',
    border: '#3A3834',
  },
  axis: '#A09A92',
  grid: 'rgba(0,0,0,0.04)',
  polarBorder: 'rgba(0,0,0,0.08)',
  heatmapEmptyCell: 'rgba(218, 214, 206, 0.45)',
  heatmapPalette: [
    'rgba(74, 89, 64, 0.14)',
    'rgba(74, 89, 64, 0.32)',
    'rgba(74, 89, 64, 0.54)',
    'rgba(74, 89, 64, 0.76)',
    '#4A5940',
  ],
  activityDivider: 'rgba(105, 101, 96, 0.45)',
  activityBar: 'rgba(74, 89, 64, 0.72)',
  /*
   * Hovered hour in the species-by-hour heatmap: a faint slate band behind the
   * whole column, with the totals bar of that hour at full strength. The band
   * alone disappears under a column of dark cells, so an outline is drawn on
   * top of everything to keep the column readable at any activity level.
   */
  activityColumnHighlight: 'rgba(105, 101, 96, 0.13)',
  activityColumnOutline: 'rgba(37, 35, 32, 0.6)',
  activityBarStrong: '#4A5940',
  activityLabel: 'rgba(105, 101, 96, 0.5)',
  activityGridMajor: 'rgba(0,0,0,0.05)',
  activityGridMinor: 'rgba(0,0,0,0.025)',
  yearlyEmptyCell: 'rgba(218, 214, 206, 0.5)',
  // Flat forest fill for the daily-activity bars (no gradient).
  hourlyBar: '#4A5940',
  hourlyBarHighlight: '#4A5940',
  hourlyBarDimmed: 'rgba(74, 89, 64, 0.14)',
  /*
   * Day/night background zones for the daily-activity chart. Understated warm
   * neutrals drawn from the paper palette rather than saturated day/night hues:
   * night reads as a soft limestone-taupe panel, day as a faint warm paper lift,
   * with just enough contrast to separate the two. Each zone is a single solid
   * fill, no vertical gradient.
   */
  dayNight: {
    night: 'rgba(105, 101, 96, 0.12)',
    day: 'rgba(236, 223, 196, 0.20)',
    // Same colors as the sunrise/sunset legend icons: --sun-gold and --night-violet.
    sunIcon: '#f2a93b',
    moonIcon: '#796ecb',
  },
  densityRgb: '74,89,64',
  /*
   * Vibrant multi-species palette: natural pigments at full saturation for perceptual separation.
   * Forest green, ochre, slate blue, teal, burnt sienna, indigo, plum, amber.
   */
  palette: ['#3D6B2E', '#C8861A', '#3B5F8A', '#2A8B7A', '#B85B35', '#4A4B8A', '#8B3D7A', '#C4A832'],
  /*
   * Warm→cool sequential ramp for the seasonality band:
   * pale sand (least probable) → orange → salmon → mauve → periwinkle → blue → deep blue (most probable).
   */
  seasonalityGradient: [
    '#F4E4BC',
    '#EDB27A',
    '#E79B8E',
    '#C99BC0',
    '#8E86C9',
    '#4E58C4',
    '#2E3AA8',
  ],
  spectrogram: {
    /*
     * Green-channel palette: black → forest green → bright lime → pale chartreuse.
     * Evokes traditional sonogram and BirdNET output; high-energy marks glow green.
     */
    stops: [
      [0.0, [10, 10, 12]],
      [0.3, [15, 52, 25]],
      [0.6, [35, 110, 50]],
      [0.8, [100, 185, 80]],
      [1.0, [228, 244, 196]],
    ],
  },
}

export const TOOLTIP_DEFAULTS = {
  backgroundColor: CHART_COLORS.tooltip.background,
  titleColor: CHART_COLORS.tooltip.title,
  bodyColor: CHART_COLORS.tooltip.body,
  borderColor: CHART_COLORS.tooltip.border,
  borderWidth: 1,
  padding: 10,
  cornerRadius: 2,
}
