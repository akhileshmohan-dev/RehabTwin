/**
 * Warms the lazy 3D replay code path (and the GLB, via useGLTF.preload in
 * ReplayCanvas) so the first "View 3D Replay" click feels instant.
 *
 * Called on hover/focus of a replay button — never during the dashboard's
 * initial load, so the first paint stays light.
 */
let warmed = false;

export function preloadSessionReplay(): void {
  if (warmed || typeof window === "undefined") return;
  warmed = true;
  // Importing ReplayCanvas triggers useGLTF.preload(MODEL_URL) at module scope.
  void import("./SessionReplayModal");
  void import("./SessionReplay3D");
  void import("./ReplayCanvas");
}
