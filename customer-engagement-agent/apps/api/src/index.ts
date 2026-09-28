import cors from 'cors';
import express from 'express';
import helmet from 'helmet';
import { z } from 'zod';
import { CUSTOMER_ENGAGEMENT_MANIFEST, runBusinessCycle } from '@cea/shared';

const app = express();
app.use(helmet());
app.use(cors({ origin: true }));
app.use(express.json({ limit: '1mb' }));

app.get('/health', (_req, res) => res.json({ ok: true, service: 'customer-engagement-agent-api', capabilities: ['C1','C2','C3','C4','C5'] }));

const lineSchema = z.object({ productId: z.string(), quantity: z.number().positive(), unitPrice: z.number().nonnegative() });
const customerSchema = z.object({ id:z.string(), businessId:z.string(), name:z.string(), phone:z.string().optional(), consentMarketing:z.boolean(), tags:z.array(z.string()), createdAt:z.string(), lastVisitAt:z.string().optional() });
const transactionSchema = z.object({ id:z.string(), businessId:z.string(), customerId:z.string(), total:z.number().nonnegative(), items:z.array(lineSchema), createdAt:z.string(), sourceAgent:z.literal('Sales') });
const productSchema = z.object({ id:z.string(), businessId:z.string(), name:z.string(), sku:z.string(), category:z.string(), stock:z.number().nonnegative(), reorderLevel:z.number().nonnegative(), marginPct:z.number(), price:z.number().nonnegative(), isActive:z.boolean(), sourceAgent:z.union([z.literal('Inventory'),z.literal('Pricing')]) });
const feedbackSchema = z.object({ id:z.string(), businessId:z.string(), customerId:z.string(), channel:z.enum(['in-store','whatsapp','sms','web','other']), message:z.string(), createdAt:z.string(), status:z.enum(['new','reviewed','resolved']) });
const bodySchema = z.object({ businessId:z.string().min(1), customers:z.array(customerSchema), transactions:z.array(transactionSchema), products:z.array(productSchema), feedback:z.array(feedbackSchema), nowIso:z.string().datetime().optional() });

app.post('/api/v1/customer-engagement/run', (req, res) => {
  const parsed = bodySchema.safeParse(req.body);
  if (!parsed.success) return res.status(400).json({ error: 'Invalid payload', issues: parsed.error.issues });
  const body = parsed.data;
  const mismatched = [...body.customers, ...body.transactions, ...body.products, ...body.feedback].some(item => item.businessId !== body.businessId);
  if (mismatched) return res.status(400).json({ error: 'Cross-business data is not allowed in one engagement cycle.' });
  const results = runBusinessCycle(body.customers, body.transactions, body.products, body.feedback, body.nowIso ?? new Date().toISOString());
  return res.json({ businessId: body.businessId, generatedAt: new Date().toISOString(), results });
});

app.get('/api/v1/customer-engagement/integration-contract', (_req, res) => res.json(CUSTOMER_ENGAGEMENT_MANIFEST));
app.get('/api/v1/customer-engagement/manifest', (_req, res) => res.json(CUSTOMER_ENGAGEMENT_MANIFEST));

app.use((_req, res) => res.status(404).json({ error: 'Not found' }));
const port = Number(process.env.PORT || 8787);
app.listen(port, () => console.log(`Customer Engagement API listening on http://localhost:${port}`));
