from app.agents.procurement.r1_supplier_comparator import SupplierComparatorAgent
from app.agents.procurement.r2_supplier_reliability import SupplierReliabilityAgent
from app.agents.procurement.r3_lead_time_risk import LeadTimeRiskAgent
from app.agents.procurement.r4_purchase_order_recommender import PurchaseOrderRecommenderAgent
from app.agents.procurement.r5_delivery_invoice_reconciliation import DeliveryInvoiceReconciliationAgent

AGENT_CLASSES = {
    "R1": SupplierComparatorAgent,
    "R2": SupplierReliabilityAgent,
    "R3": LeadTimeRiskAgent,
    "R4": PurchaseOrderRecommenderAgent,
    "R5": DeliveryInvoiceReconciliationAgent,
}
