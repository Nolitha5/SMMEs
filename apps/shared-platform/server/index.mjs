import { createApp } from './app.mjs';
import { config } from './config.mjs';

const app = createApp();
app.listen(config.port, () => {
  console.log(`Shared platform API listening on http://localhost:${config.port}`);
});
