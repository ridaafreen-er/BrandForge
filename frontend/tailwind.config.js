module.exports = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: { ink: "#0C0F14", panel: "#141922", line: "#262E3B", mute: "#8B97A8", ember: "#FFB020", steel: "#7AA2F7", ok: "#4ADE80", bad: "#FB7185" },
    fontFamily: { display: ["var(--font-display)", "sans-serif"], body: ["var(--font-body)", "sans-serif"] },
    keyframes: { pour: { "0%,100%": { opacity: ".25", transform: "translateY(6px)" }, "50%": { opacity: "1", transform: "translateY(0)" } }, flow: { to: { strokeDashoffset: "-24" } } },
    animation: { pour: "pour 2.4s ease-in-out infinite", flow: "flow 1s linear infinite" },
  } },
  plugins: [],
};
