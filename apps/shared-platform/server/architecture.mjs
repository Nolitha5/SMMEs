import fs from 'node:fs';
import path from 'node:path';
import { ROOT } from './config.mjs';

const FOUNDATION_ROOT = path.resolve(ROOT, '..', '..');
const APP_ARCHITECTURE = path.join(ROOT, 'architecture');
const FOUNDATION_ARCHITECTURE = path.join(FOUNDATION_ROOT, 'architecture');

function resolveArchitectureFile(name) {
  // The repository-level architecture directory is the canonical source of truth.
  // Use the app-local copy only for standalone/container builds where the repository
  // architecture directory is intentionally not present.
  const canonical = path.join(FOUNDATION_ARCHITECTURE, name);
  if (fs.existsSync(canonical)) return canonical;
  return path.join(APP_ARCHITECTURE, name);
}

function load(name) {
  return JSON.parse(fs.readFileSync(resolveArchitectureFile(name), 'utf8'));
}

export const capabilityRegistry = load('capability-registry.v1.json');
export const pricingStatus = load('pricing-integration-status.v2.json');
export const demandStatus = load('demand-live-source-status.v1.json');
export const backendStatus = load('backend-completion-status.v1.json');
export const collectionRegistry = load('collection-registry-target.v4.json');

export function normalizedCapabilities() {
  return capabilityRegistry.capabilities.map((item) => {
    let implementationStatus = item.implementationStatus;
    if (item.domain === 'pricing') {
      implementationStatus = pricingStatus.capabilities?.[item.capabilityId]?.status ?? implementationStatus;
    }
    if (item.domain === 'demand') {
      implementationStatus = demandStatus.capabilities?.[item.capabilityId]?.status ?? implementationStatus;
    }
    return { ...item, implementationStatus };
  });
}
