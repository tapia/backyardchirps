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
  // Same as --sheet, the card background: heatmap cells are outlined in it to leave a gap.
  heatmapCellGap: '#fdfcfa',
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
   * Hovered hour in the species-by-hour heatmap: a faint slate tint over the
   * whole column, with the totals bar of that hour at full strength.
   */
  activityColumnHighlight: 'rgba(105, 101, 96, 0.13)',
  activityBarStrong: '#4A5940',
  activityLabel: 'rgba(105, 101, 96, 0.5)',
  // Short ticks beside the 12AM, 6AM, 12PM and 6PM labels of the activity map.
  activityHourTick: 'rgba(0,0,0,0.13)',
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
   * Species ranking (ribbon) chart, assigned in the order of the species list and repeated
   * past the tenth species.
   */
  /*
   * The rest of the species ranking chart. paper and ink are the same as --ribbon-paper and
   * --ribbon-ink, which the card and its species buttons use.
   */
  ribbon: {
    paper: '#f7f6f2',
    ink: '#1f1f1f',
    muted: '#6b6a66',
    grid: '#e6e4dd',
  },
  ribbonPalette: [
    '#2d6a4f',
    '#f4a261',
    '#264653',
    '#2a9d8f',
    '#e76f51',
    '#6d597a',
    '#b56576',
    '#e9c46a',
    '#8ab17d',
    '#7f5539',
  ],
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
