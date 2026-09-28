import type { Customer, Feedback, Product, Transaction } from '../types.js';
import { isoDaysAgo } from '../utils.js';

export const DEMO_BUSINESS_ID = 'demo-spaza-001';

export function demoData(now = new Date()): { customers: Customer[]; transactions: Transaction[]; products: Product[]; feedback: Feedback[] } {
  const b = DEMO_BUSINESS_ID;
  const customers: Customer[] = [
    { id:'cus-thandi', businessId:b, name:'Thandi Mokoena', phone:'082 *** 1142', consentMarketing:true, tags:['weekday'], createdAt:isoDaysAgo(190,now), lastVisitAt:isoDaysAgo(3,now) },
    { id:'cus-sipho', businessId:b, name:'Sipho Dlamini', phone:'073 *** 8021', consentMarketing:true, tags:['family'], createdAt:isoDaysAgo(260,now), lastVisitAt:isoDaysAgo(58,now) },
    { id:'cus-lerato', businessId:b, name:'Lerato Molefe', consentMarketing:false, tags:[], createdAt:isoDaysAgo(8,now), lastVisitAt:isoDaysAgo(8,now) },
    { id:'cus-kagiso', businessId:b, name:'Kagiso Nkosi', phone:'071 *** 6630', consentMarketing:true, tags:['bulk'], createdAt:isoDaysAgo(350,now), lastVisitAt:isoDaysAgo(1,now) },
    { id:'cus-zanele', businessId:b, name:'Zanele Khumalo', phone:'079 *** 9920', consentMarketing:true, tags:['value'], createdAt:isoDaysAgo(220,now), lastVisitAt:isoDaysAgo(16,now) },
    { id:'cus-themba', businessId:b, name:'Themba Maseko', consentMarketing:true, tags:[], createdAt:isoDaysAgo(420,now), lastVisitAt:isoDaysAgo(112,now) }
  ];
  const products: Product[] = [
    { id:'prod-maize', businessId:b, name:'Maize Meal 5kg', sku:'MM-5KG', category:'Staples', stock:42, reorderLevel:12, marginPct:19, price:84.99, isActive:true, sourceAgent:'Inventory' },
    { id:'prod-milk', businessId:b, name:'Long Life Milk 1L', sku:'MLK-1L', category:'Dairy', stock:54, reorderLevel:18, marginPct:16, price:18.99, isActive:true, sourceAgent:'Inventory' },
    { id:'prod-bread', businessId:b, name:'Brown Bread 700g', sku:'BRD-700', category:'Bakery', stock:8, reorderLevel:10, marginPct:14, price:19.49, isActive:true, sourceAgent:'Inventory' },
    { id:'prod-oil', businessId:b, name:'Cooking Oil 2L', sku:'OIL-2L', category:'Staples', stock:31, reorderLevel:8, marginPct:22, price:79.99, isActive:true, sourceAgent:'Inventory' },
    { id:'prod-soap', businessId:b, name:'Bath Soap 175g', sku:'SOAP-175', category:'Household', stock:61, reorderLevel:15, marginPct:28, price:15.99, isActive:true, sourceAgent:'Inventory' }
  ];
  let n=0;
  const tx=(customerId:string, days:number, total:number, items:Transaction['items']):Transaction => ({id:`tx-${++n}`,businessId:b,customerId,total,items,createdAt:isoDaysAgo(days,now),sourceAgent:'Sales'});
  const transactions: Transaction[] = [
    tx('cus-thandi',3,167,[{productId:'prod-maize',quantity:1,unitPrice:84.99},{productId:'prod-oil',quantity:1,unitPrice:79.99}]),
    tx('cus-thandi',14,104,[{productId:'prod-maize',quantity:1,unitPrice:84.99},{productId:'prod-bread',quantity:1,unitPrice:19.49}]),
    tx('cus-thandi',28,84.99,[{productId:'prod-maize',quantity:1,unitPrice:84.99}]),
    tx('cus-thandi',47,120,[{productId:'prod-milk',quantity:4,unitPrice:18.99},{productId:'prod-soap',quantity:2,unitPrice:15.99}]),
    tx('cus-sipho',58,250,[{productId:'prod-maize',quantity:2,unitPrice:84.99},{productId:'prod-oil',quantity:1,unitPrice:79.99}]),
    tx('cus-sipho',93,180,[{productId:'prod-maize',quantity:1,unitPrice:84.99}]),
    tx('cus-lerato',8,38,[{productId:'prod-milk',quantity:1,unitPrice:18.99},{productId:'prod-bread',quantity:1,unitPrice:19.49}]),
    tx('cus-kagiso',1,470,[{productId:'prod-maize',quantity:3,unitPrice:84.99},{productId:'prod-oil',quantity:2,unitPrice:79.99}]),
    tx('cus-kagiso',9,315,[{productId:'prod-maize',quantity:2,unitPrice:84.99},{productId:'prod-milk',quantity:5,unitPrice:18.99}]),
    tx('cus-kagiso',18,410,[{productId:'prod-oil',quantity:3,unitPrice:79.99},{productId:'prod-soap',quantity:8,unitPrice:15.99}]),
    tx('cus-kagiso',27,230,[{productId:'prod-maize',quantity:2,unitPrice:84.99}]),
    tx('cus-kagiso',36,360,[{productId:'prod-oil',quantity:3,unitPrice:79.99}]),
    tx('cus-kagiso',45,295,[{productId:'prod-maize',quantity:2,unitPrice:84.99}]),
    tx('cus-kagiso',54,330,[{productId:'prod-soap',quantity:10,unitPrice:15.99}]),
    tx('cus-kagiso',63,415,[{productId:'prod-maize',quantity:3,unitPrice:84.99}]),
    tx('cus-zanele',16,68,[{productId:'prod-milk',quantity:2,unitPrice:18.99},{productId:'prod-soap',quantity:2,unitPrice:15.99}]),
    tx('cus-zanele',39,52,[{productId:'prod-bread',quantity:1,unitPrice:19.49},{productId:'prod-soap',quantity:2,unitPrice:15.99}]),
    tx('cus-zanele',70,67,[{productId:'prod-milk',quantity:2,unitPrice:18.99}]),
    tx('cus-themba',112,170,[{productId:'prod-maize',quantity:2,unitPrice:84.99}])
  ];
  const feedback: Feedback[] = [
    {id:'fb-1',businessId:b,customerId:'cus-thandi',channel:'whatsapp',message:'Great service today, staff were friendly and fast.',createdAt:isoDaysAgo(3,now),status:'reviewed'},
    {id:'fb-2',businessId:b,customerId:'cus-sipho',channel:'whatsapp',message:'I am angry. The queue was slow and I got the wrong change. I want this fixed.',createdAt:isoDaysAgo(57,now),status:'new'},
    {id:'fb-3',businessId:b,customerId:'cus-zanele',channel:'in-store',message:'Prices are a bit expensive but the shop is clean.',createdAt:isoDaysAgo(15,now),status:'reviewed'}
  ];
  return { customers, transactions, products, feedback };
}
