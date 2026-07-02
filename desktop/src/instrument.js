'use strict';

const Sentry = require('@sentry/node');

const sentryOptions = {
  dsn: process.env.SENTRY_DSN_DESKTOP || undefined,
  environment: process.env.SENTRY_ENVIRONMENT || 'production',
  release: process.env.SENTRY_RELEASE || undefined,
  dataCollection: {},
};

// Only initialize when a DSN is configured; otherwise stay a no-op so a
// missing env var never blocks the desktop app from starting.
if (sentryOptions.dsn) {
  Sentry.init(sentryOptions);
}

module.exports = { sentryOptions };
