import { defineConfig } from '@hey-api/openapi-ts';

// Generates the typed API client from the running FastAPI backend's OpenAPI
// schema. Start the backend (http://localhost:8000) before `npm run generate-client`.
// openapi-ts >= 0.66 replaced the `--client` CLI flag with the plugin system;
// the axios client now ships as the separate `@hey-api/client-axios` package.
export default defineConfig({
  input: 'http://localhost:8000/openapi.json',
  output: './src/client',
  plugins: ['@hey-api/client-axios'],
});
