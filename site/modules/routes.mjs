export const VIEWS=Object.freeze([
  ["dashboard","home","Overview"],["applications","file","Applications"],["discovery","database","Discovery"],
  ["readiness","check","Readiness"],["documents","file","Documents"],["operations","layers","Operations"],["actions","check","Actions"],
  ["ledger","check","Task ledger"],["calendar","calendar","Calendar"],["pipeline","columns","Pipeline"],
  ["contacts","users","Contacts"],["updates","clock","Updates"],["compare","compare","Compare"],
  ["review","shield","Verification"],["archive","archive","Archive"],["sources","database","Sources"],
  ["ai","sparkles","Copilot"],["agents","bot","Agents"],["automations","flow","Automations"],
  ["activity","activity","Run history"],["source-observations","database","Source observations"],["onboarding","check","First-run setup"],["deployment","settings","Deployment"],["settings","settings","Settings"]
].map(entry=>Object.freeze(entry)));

const ALIASES=Object.freeze({
  home:"dashboard",
  opportunities:"applications",
  research:"discovery",
  dossier:"documents",
  document:"documents",
  models:"settings",
  providers:"settings",
  connect:"settings",
  assistant:"ai",
  copilot:"ai",
  workflows:"automations",
  setup:"deployment",
  "get-started":"onboarding",
  "first-run":"onboarding",
  runtime:"deployment",
  verification:"review",
  "source-drift":"source-observations",
  observations:"source-observations",
  "source-monitor":"source-observations"
});
const IDS=new Set(VIEWS.map(([id])=>id));

export function resolveWorkspaceRoute(hash) {
  const input=String(hash??"").trim().replace(/^#/,"").toLowerCase();
  const value=/^[a-z][a-z0-9_-]{0,40}$/.test(input)?input:"";
  const destination=Object.hasOwn(ALIASES,value)?ALIASES[value]:value;
  return IDS.has(destination)?destination:"dashboard";
}
