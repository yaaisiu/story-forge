// Landing — a deliberately empty placeholder that exists only so the shell has
// something to render at "/" while Session 5 stands up the providers. Session 6
// replaces this with the real upload screen (file picker, drag-drop, language
// indicator — see PLAN_SHORT.md Session 6 and spec §7 step 1).
//
// `data-testid="landing-placeholder"` is the stable hook the shell render test
// asserts on; the visible copy can change in Session 6 without touching the test.
export function Landing() {
  return (
    <section data-testid="landing-placeholder">
      <h1>Story Forge</h1>
      <p>Frontend shell is up. Upload UI lands in the next session.</p>
    </section>
  );
}
