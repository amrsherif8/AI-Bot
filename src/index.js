import { Container, getContainer } from "@cloudflare/containers";

const FORWARDED = ["GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_FALLBACK_MODEL"];

export class FunkeContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "10m";

  constructor(ctx, env) {
    super(ctx, env);
    this.envVars = Object.fromEntries(
      FORWARDED.filter((name) => env[name]).map((name) => [name, String(env[name])])
    );
  }
}

export default {
  async fetch(request, env) {
    return getContainer(env.FUNKE).fetch(request);
  },
};
