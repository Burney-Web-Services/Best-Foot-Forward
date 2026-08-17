// BFF About — a static "what is this thing" page pointing at the public site.
//
// mystery6's plugin loader requires every plugin to export a Router as default
// (src/plugins/loader.js), even when the plugin is frontend-only. This router
// intentionally has no routes; all the content lives in public/bff-about.js.

import { Router } from 'express';

const router = Router();

export default router;
