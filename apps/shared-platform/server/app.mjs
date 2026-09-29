import express from 'express';
import cors from 'cors';
import fs from 'node:fs';
import path from 'node:path';
import { config, ROOT } from './config.mjs';
import { getFirebaseState, getFirebaseServices } from './firebase.mjs';
import { requireUser, requireBusinessAccess, requireDataEditor } from './auth.mjs';
import { loadWorkspace, recordRecommendationDecision } from './firestore-data.mjs';
import { backendStatus, collectionRegistry } from './architecture.mjs';
import {
  loadDataCatalog,
  listDataRecords,
  validateBusinessData,
  importBusinessData,
  saveBusinessDataRecord
} from './data-store.mjs';
import { getProcessingReadiness, processBusiness } from './process/processing-service.mjs';

function dataError(res, error) {
  const status = error.code === 'FIREBASE_UNAVAILABLE' ? 503 :
    ['VALIDATION_FAILED', 'IDENTITY_CHANGE', 'UNKNOWN_DATASET'].includes(error.code) ? 400 : 500;
  return res.status(status).json({ error: error.message, details: error.details || [] });
}

export function createApp() {
  const app = express();
  app.disable('x-powered-by');
  app.use((_req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
    if (process.env.NODE_ENV === 'production') {
      res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
    }
    next();
  });
  if (config.webOrigin) {
    const allowedOrigins = config.webOrigin.split(',').map((value) => value.trim()).filter(Boolean);
    app.use(cors({ origin: allowedOrigins.length === 1 ? allowedOrigins[0] : allowedOrigins, credentials: true }));
  }
  app.use(express.json({ limit: '10mb' }));

  app.get('/api/health', (_req, res) => {
    res.json({
      ok: true,
      service: 'shared-platform-api',
      authMode: config.authMode,
      firebase: getFirebaseState(),
      backendStatus: backendStatus.currentStatus
    });
  });

  app.get('/api/ready', async (_req, res) => {
    const { db, error } = getFirebaseServices();
    if (!db) return res.status(503).json({ ok: false, error: error?.message || 'Firestore is unavailable.' });
    try {
      await db.doc(`businesses/${config.businessId}`).get();
      return res.json({ ok: true, service: 'SME Operations', firebase: 'connected' });
    } catch (cause) {
      return res.status(503).json({ ok: false, error: cause instanceof Error ? cause.message : String(cause) });
    }
  });

  app.get('/api/client-config', (_req, res) => {
    res.setHeader('Cache-Control', 'no-store');
    res.json({
      authMode: config.authMode,
      businessId: config.businessId,
      firebase: config.authMode === 'firebase' ? {
        apiKey: config.firebaseWebApiKey || null,
        authDomain: config.firebaseWebAuthDomain || null,
        projectId: config.firebaseProjectId || null,
        appId: config.firebaseWebAppId || null
      } : null
    });
  });

  app.get('/api/architecture', requireUser, (_req, res) => {
    res.json({
      backendStatus,
      schemaVersion: collectionRegistry.schemaTargetVersion,
      collections: collectionRegistry.collections
    });
  });

  app.get(
    '/api/businesses/:businessId/workspace',
    requireUser,
    requireBusinessAccess,
    async (req, res) => {
      try {
        res.json(await loadWorkspace(req.params.businessId));
      } catch (error) {
        res.status(error.code === 'FIREBASE_UNAVAILABLE' ? 503 : 500).json({ error: error.message });
      }
    }
  );

  app.get(
    '/api/businesses/:businessId/data',
    requireUser,
    requireBusinessAccess,
    async (req, res) => {
      try {
        res.json({ datasets: await loadDataCatalog(req.params.businessId) });
      } catch (error) {
        dataError(res, error);
      }
    }
  );

  app.get(
    '/api/businesses/:businessId/data/:dataset',
    requireUser,
    requireBusinessAccess,
    async (req, res) => {
      try {
        res.json(await listDataRecords(req.params.businessId, req.params.dataset, req.query.limit));
      } catch (error) {
        dataError(res, error);
      }
    }
  );

  app.post(
    '/api/businesses/:businessId/data/:dataset/validate',
    requireUser,
    requireBusinessAccess,
    requireDataEditor,
    async (req, res) => {
      try {
        res.json(await validateBusinessData(req.params.businessId, req.params.dataset, req.body?.records || []));
      } catch (error) {
        dataError(res, error);
      }
    }
  );

  app.post(
    '/api/businesses/:businessId/data/:dataset/import',
    requireUser,
    requireBusinessAccess,
    requireDataEditor,
    async (req, res) => {
      try {
        res.json(await importBusinessData({
          businessId: req.params.businessId,
          datasetKey: req.params.dataset,
          records: req.body?.records || [],
          actor: req.user.uid
        }));
      } catch (error) {
        dataError(res, error);
      }
    }
  );

  app.post(
    '/api/businesses/:businessId/data/:dataset',
    requireUser,
    requireBusinessAccess,
    requireDataEditor,
    async (req, res) => {
      try {
        res.json(await saveBusinessDataRecord({
          businessId: req.params.businessId,
          datasetKey: req.params.dataset,
          input: req.body?.record || {},
          actor: req.user.uid
        }));
      } catch (error) {
        dataError(res, error);
      }
    }
  );

  app.put(
    '/api/businesses/:businessId/data/:dataset/:recordId',
    requireUser,
    requireBusinessAccess,
    requireDataEditor,
    async (req, res) => {
      try {
        res.json(await saveBusinessDataRecord({
          businessId: req.params.businessId,
          datasetKey: req.params.dataset,
          input: req.body?.record || {},
          actor: req.user.uid,
          existingId: req.params.recordId
        }));
      } catch (error) {
        dataError(res, error);
      }
    }
  );

  app.get(
    '/api/businesses/:businessId/process/readiness',
    requireUser,
    requireBusinessAccess,
    async (req, res) => {
      try {
        res.json(await getProcessingReadiness(req.params.businessId));
      } catch (error) {
        res.status(error.code === 'FIREBASE_UNAVAILABLE' ? 503 : 500).json({ error: error.message });
      }
    }
  );

  app.post(
    '/api/businesses/:businessId/process',
    requireUser,
    requireBusinessAccess,
    requireDataEditor,
    async (req, res) => {
      try {
        res.json(await processBusiness({ businessId: req.params.businessId, actor: req.user.uid }));
      } catch (error) {
        const status = error.code === 'PROCESSING_ALREADY_RUNNING' ? 409 : error.code === 'PROCESSING_NOT_READY' ? 400 : error.code === 'FIREBASE_UNAVAILABLE' ? 503 : 500;
        res.status(status).json({ error: error.message });
      }
    }
  );

  app.post(
    '/api/businesses/:businessId/recommendations/:recommendationId/decision',
    requireUser,
    requireBusinessAccess,
    requireDataEditor,
    async (req, res) => {
      try {
        const result = await recordRecommendationDecision({
          businessId: req.params.businessId,
          recommendationId: req.params.recommendationId,
          reviewer: req.user.uid,
          decision: req.body?.decision,
          reason: req.body?.reason,
          modifiedAction: req.body?.modifiedAction
        });
        res.json(result);
      } catch (error) {
        res.status(400).json({ error: error.message });
      }
    }
  );

  const webRoot = path.join(ROOT, 'dist', 'web');
  const webIndex = path.join(webRoot, 'index.html');
  if (process.env.NODE_ENV === 'production' && fs.existsSync(webIndex)) {
    app.use(express.static(webRoot, { index: false, maxAge: '1y', immutable: true }));
    app.use((req, res, next) => {
      if (req.path.startsWith('/api/')) return res.status(404).json({ error: `Unknown route: ${req.method} ${req.path}` });
      if (req.method === 'GET') { res.setHeader('Cache-Control', 'no-store'); return res.sendFile(webIndex); }
      return next();
    });
  } else {
    app.use((req, res) => res.status(404).json({ error: `Unknown route: ${req.method} ${req.path}` }));
  }
  return app;
}
